"""Regenerate every JSON artifact the frontend reads, from /data/raw only.

    python -m pipeline.build

No network access. Verify this with the wifi off before the demo: nothing in
here, or anywhere downstream of here, is allowed to make a request.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline import cases, detect, heatmap as heatmap_mod, xml_export
from pipeline.contracts import OBSERVATIONS_PATH, json_safe
from pipeline.expectations import attach_expectations
from pipeline.generalise import assign_localities, summarise
from pipeline.ingest import agmarknet_export, gazette, necc_real, qcommerce, reports, ridehail
from pipeline.model import benchmark_band, fit_band, predict_band

OUT = Path("web/public/data")

# Items that do not come from Agmarknet and so have no source-provided name.
FALLBACK_LABELS = {"auto_ride": "Autorickshaw fares", "egg_table": "Table eggs"}

# The model learns from all the history there is; detection runs only on the
# recent window. An officer inspects what is happening now — a run of high
# prices in 2022 is not an inspection target, and with six years of data every
# series eventually has one. Without this the queue reached 48 flags, which is
# not a queue.
DETECTION_WINDOW_DAYS = 90
# Real sources for the reference rates, synthetic observations for the q-commerce,
# ride-hail and field-report tiers. Swap those three as real collection lands.
SOURCES = [agmarknet_export, necc_real, qcommerce, ridehail, reports]


def _write(name: str, payload) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    path.write_text(json.dumps(json_safe(payload), indent=1, sort_keys=False) + "\n")
    print(f"    wrote {path} ({path.stat().st_size / 1024:.0f} kB)")


def parse_sources(verbose: bool = True) -> pd.DataFrame:
    """Parse every source into one frame.

    The single parse path. The API server calls this too — when it had its own
    copy the two drifted, and the server served a different queue from the one
    `pipeline.build` wrote.
    """
    log = print if verbose else (lambda *a, **k: None)
    frames = []
    for mod in SOURCES:
        # the real Agmarknet export is ingested in full: the band model is better
        # for the wider cross-section, and the three commodities section 8 allows
        # produce no flags at all on real data
        df = mod.parse(demo_only=False) if mod is agmarknet_export else mod.parse()
        log(f"    {mod.__name__.split('.')[-1]:11s} {len(df):6d} observations")
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def ingest() -> pd.DataFrame:
    print("  ingest")
    obs = parse_sources()
    Path("data/processed").mkdir(parents=True, exist_ok=True)
    obs.to_parquet(OBSERVATIONS_PATH, index=False)
    print(f"    -> {OBSERVATIONS_PATH} ({len(obs)} rows)")
    return obs


def build_references(obs: pd.DataFrame) -> pd.DataFrame:
    dates = sorted(obs["date"].unique())
    egg_zones = sorted(obs.loc[obs["item"] == "egg_table", "location"].unique())
    egg_zones = [z for z in egg_zones if z != "necc_declared"]
    return pd.concat([necc_real.references(egg_zones), gazette.references(dates),
                      agmarknet_export.references(obs)], ignore_index=True)


# How much history to draw either side of a flagged window. Enough to judge
# whether the flagged period is unusual; not so much that a 10-day finding
# becomes an invisible sliver against two years of chart.
CHART_CONTEXT_DAYS = 45


def _clip_to_context(g: pd.DataFrame, window: dict[str, str]) -> pd.DataFrame:
    start = (pd.Timestamp(window["start"]) - pd.Timedelta(days=CHART_CONTEXT_DAYS))
    end = (pd.Timestamp(window["end"]) + pd.Timedelta(days=CHART_CONTEXT_DAYS))
    d = pd.to_datetime(g["date"])
    return g[(d >= start) & (d <= end)]


def _daily_band(g: pd.DataFrame) -> list[dict]:
    d = (g.groupby("date")
         .agg(price=("price", "median"), lo=("expected_lo", "median"),
              mid=("expected_mid", "median"), hi=("expected_hi", "median"),
              n=("price", "size"))
         .reset_index().sort_values("date"))
    return d.to_dict("records")


def _egg_spread(df: pd.DataFrame, location: str, window: dict | None = None) -> dict:
    """Three lines: the declared rate, commercial listings, field reports."""
    declared = (df[df["source"] == "necc"].groupby("date")["price"].median()
                .rename("declared"))
    zone = df[(df["item"] == "egg_table") & (df["location"] == location)]
    if window is not None:
        zone = _clip_to_context(zone, window)
    listed = zone[zone["tier"] == "B"].groupby("date")["price"].median().rename("listed")
    field = zone[zone["tier"] == "C"].groupby("date")["price"].median().rename("reported")
    merged = pd.concat([declared, listed, field], axis=1).dropna(subset=["declared"])
    merged = merged[merged.index >= zone["date"].min()]
    return {"lines": merged.reset_index().rename(columns={"index": "date"})
            .to_dict("records")}


def _auto_scatter(df: pd.DataFrame, location: str, window: dict | None = None) -> dict:
    """Fare against distance, with the notified schedule overlaid."""
    sched = gazette.schedule()
    z = df[(df["item"] == "auto_ride") & (df["location"] == location)
           & df["distance_km"].notna()]
    if window is not None:
        z = _clip_to_context(z, window)
    pts = (z[["distance_km", "price", "tier", "date"]]
           .rename(columns={"distance_km": "km"}).to_dict("records"))
    km = np.arange(1.0, 8.51, 0.5)
    return {
        "points": pts,
        "gazette_line": [{"km": float(k), "fare": gazette.fare_for(float(k), sched)}
                         for k in km],
        "schedule": {"minimum_fare": sched["minimum_fare"],
                     "included_km": sched["minimum_fare_included_km"],
                     "per_km_after": sched["per_km_after"]},
    }


def chart_for(df: pd.DataFrame, flag: dict) -> dict:
    item, location = flag["item"], flag["location"]
    g = df[(df["item"] == item) & (df["location"] == location)]
    g = _clip_to_context(g, flag["window"])
    payload = {"kind": "band", "window": flag["window"], "daily": _daily_band(g)}
    if item == "egg_table":
        payload["kind"] = "spread"
        payload.update(_egg_spread(df, location, flag["window"]))
    elif item == "auto_ride":
        payload["kind"] = "scatter"
        payload.update(_auto_scatter(df, location, flag["window"]))
    return payload


def compute(obs: pd.DataFrame, model=None, verbose: bool = True) -> dict:
    """Observations in, artifacts out. The single computation path.

    `pipeline.build` writes the result to disk; the API server holds it in memory
    and recomputes when the evidence set changes. Both call this, so the offline
    build and the live server can never drift apart.

    Pass `model` to reuse a fitted band. A citizen report does not change the
    Agmarknet backbone the band is fitted on, so refitting per report would be
    wasted work.
    """
    log = print if verbose else (lambda *a, **k: None)

    # Collapse nearby, same-price reporting points into one locality before
    # anything counts corroboration.
    obs = obs.copy()
    obs["unit_id"] = assign_localities(obs)
    gen = summarise(obs, obs["unit_id"])
    log(f"  generalise   {gen['report_points']} report points -> "
        f"{gen['report_localities']} localities ({gen['collapsed']} collapsed)")

    refs = build_references(obs)
    log(f"  references   {len(refs)} rows, "
        f"{refs['citation'].nunique()} distinct citations")

    if model is None:
        log("  model")
        model = fit_band(obs)
        for k, v in model.metrics.items():
            log(f"    {k:16s} {v}")
    banded = predict_band(model, obs)
    scored = attach_expectations(banded)
    judged = scored[~scored["is_reference_series"]]

    cutoff = (pd.to_datetime(judged["date"].max())
              - pd.Timedelta(days=DETECTION_WINDOW_DAYS)).strftime("%Y-%m-%d")
    recent = judged[judged["date"] >= cutoff]
    log(f"  detect       window {cutoff} -> {judged['date'].max()} "
        f"({len(recent)} of {len(judged)} observations)")
    flags = detect.run_all(recent) if verbose else _quiet_detect(recent)

    log("  cases")
    labels = dict(FALLBACK_LABELS)
    try:
        labels.update(agmarknet_export.display_labels())
    except Exception as exc:                      # never let labelling break a build
        log(f"    display labels unavailable: {exc}")
    cases.set_item_labels(labels)
    queue, all_flags, case_files, charts = [], [], {}, {}
    for flag in flags:
        w = judged[(judged["item"] == flag["item"])
                   & (judged["location"] == flag["location"])
                   & (judged["date"] >= flag["window"]["start"])
                   & (judged["date"] <= flag["window"]["end"])]
        distinct = int(w["unit_id"].nunique())
        flag["distinct_sellers"] = distinct
        flag["basis"] = str(w["basis"].mode().iloc[0]) if not w.empty else "model"
        flag["citation"] = str(w["citation"].dropna().iloc[0]) if w["citation"].notna().any() else ""

        flag = cases.apply_evidence_floor(flag, distinct)
        all_flags.append(flag)
        if not cases.in_queue(flag):
            log(f"    {flag['flag_id']} downgraded to tier 1 and excluded: "
                f"{flag['evidence_floor']}")
            continue
        queue.append(flag)
        # charts draw from the full frame: the reference series is excluded from
        # detection but it is exactly what the egg spread chart plots against
        charts[flag["flag_id"]] = chart_for(scored, flag)
        case_files[flag["flag_id"]] = cases.build_case(flag)

    # An officer inspects a market, not a flag. Four findings at one market is
    # one visit, so the queue is grouped by location: the strongest finding
    # leads and the rest travel with it as supporting evidence. Without this the
    # queue reads as one market repeated, and the inspection count is inflated.
    def _gap(f: dict) -> float:
        return abs(f["observed"]["median"] / max(f["expected"]["rate"], 1e-9) - 1)

    groups: dict[str, list[dict]] = {}
    for f in queue:
        groups.setdefault(f["location"], []).append(f)

    for location, members in groups.items():
        members.sort(key=lambda f: (-f["tier"], -_gap(f)))
        for rank, f in enumerate(members):
            f["group_id"] = location
            f["group_size"] = len(members)
            f["group_rank"] = rank
            f["group_primary"] = rank == 0

    ordered = sorted(groups.values(),
                     key=lambda m: (-m[0]["tier"], -_gap(m[0])))
    queue = [f for members in ordered for f in members]

    meta = {
        "data_through": str(obs["date"].max()),
        "data_from": str(obs["date"].min()),
        "observations": int(len(obs)),
        "locations_monitored": int(obs["location"].nunique()),
        "items_monitored": int(obs["item"].nunique()),
        "rejected_reports": int(reports.REJECTED.get("no_geotag_or_timestamp", 0)),
        "flags_total": len(all_flags),
        "flags_in_queue": len(queue),
        "inspections": len({f["location"] for f in queue}),
        "flags_excluded_evidence_floor": len(all_flags) - len(queue),
        "model": model.metrics,
        "model_benchmark": benchmark_band(model, obs),
        "thresholds": detect.THRESHOLDS,
        "generaliser": gen,
        "item_labels": {k: v for k, v in labels.items()
                        if k in {f["item"] for f in all_flags}
                        | {"tomato", "onion", "potato", "brinjal", "carrot"}},
        "tier_counts": {str(k): int(v) for k, v in
                        pd.Series([f["tier"] for f in queue]).value_counts().items()},
        "sources": sorted(obs["source"].unique().tolist()),
    }
    grid = heatmap_mod.build(scored, window_days=DETECTION_WINDOW_DAYS)
    log(f"  heatmap      {grid['totals'].get('cells', 0)} cell(s) at "
        f"{heatmap_mod.CELL_M:.0f}m from {grid['totals'].get('reports_shown', 0)} "
        f"of {grid['totals'].get('reports', 0)} field reports "
        f"({grid.get('suppressed_cells', 0)} below the evidence floor)")

    log(f"\n  {len(queue)} finding(s) across "
        f"{len({f['location'] for f in queue})} market(s) for inspection, "
        f"{len(all_flags) - len(queue)} excluded by the evidence floor")
    return {"queue": queue, "flags": all_flags, "cases": case_files,
            "charts": charts, "meta": meta, "heatmap": grid, "model": model}


def _quiet_detect(judged: pd.DataFrame) -> list[dict]:
    import io
    import contextlib
    with contextlib.redirect_stdout(io.StringIO()):
        return detect.run_all(judged)


def main() -> None:
    print("building (offline; no network access)")
    obs = ingest()
    result = compute(obs)
    for name in ("queue", "flags", "cases", "charts", "meta", "heatmap"):
        _write(f"{name}.json", result[name])

    # the same case files as XML, checked against schema/case-file.xsd
    generated = str(obs["date"].max())
    tree = xml_export.build_case_set(result["cases"], result["flags"], generated)
    xml_text = xml_export.to_string(tree.getroot())
    xml_export.validate(xml_text)
    path = OUT / "cases.xml"
    path.write_text(xml_text)
    print(f"    wrote {path} ({path.stat().st_size / 1024:.0f} kB, schema-valid)")


if __name__ == "__main__":
    main()
