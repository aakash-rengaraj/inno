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

from pipeline import cases, detect
from pipeline.contracts import OBSERVATIONS_PATH, json_safe
from pipeline.expectations import attach_expectations
from pipeline.generalise import assign_localities, summarise
from pipeline.ingest import agmarknet, gazette, necc, qcommerce, reports, ridehail
from pipeline.model import fit_band, predict_band

OUT = Path("web/public/data")
SOURCES = [agmarknet, necc, qcommerce, ridehail, reports]


def _write(name: str, payload) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    path.write_text(json.dumps(json_safe(payload), indent=1, sort_keys=False) + "\n")
    print(f"    wrote {path} ({path.stat().st_size / 1024:.0f} kB)")


def ingest() -> pd.DataFrame:
    print("  ingest")
    frames = []
    for mod in SOURCES:
        df = mod.parse()
        print(f"    {mod.__name__.split('.')[-1]:11s} {len(df):6d} observations")
        frames.append(df)
    obs = pd.concat(frames, ignore_index=True)
    Path("data/processed").mkdir(parents=True, exist_ok=True)
    obs.to_parquet(OBSERVATIONS_PATH, index=False)
    print(f"    -> {OBSERVATIONS_PATH} ({len(obs)} rows)")
    return obs


def build_references(obs: pd.DataFrame) -> pd.DataFrame:
    dates = sorted(obs["date"].unique())
    return pd.concat([necc.references(), gazette.references(dates),
                      agmarknet.references(obs)], ignore_index=True)


def _daily_band(g: pd.DataFrame) -> list[dict]:
    d = (g.groupby("date")
         .agg(price=("price", "median"), lo=("expected_lo", "median"),
              mid=("expected_mid", "median"), hi=("expected_hi", "median"),
              n=("price", "size"))
         .reset_index().sort_values("date"))
    return d.to_dict("records")


def _egg_spread(df: pd.DataFrame, location: str) -> dict:
    """Three lines: the declared rate, commercial listings, field reports."""
    declared = (df[df["source"] == "necc"].groupby("date")["price"].median()
                .rename("declared"))
    zone = df[(df["item"] == "egg_table") & (df["location"] == location)]
    listed = zone[zone["tier"] == "B"].groupby("date")["price"].median().rename("listed")
    field = zone[zone["tier"] == "C"].groupby("date")["price"].median().rename("reported")
    merged = pd.concat([declared, listed, field], axis=1).dropna(subset=["declared"])
    merged = merged[merged.index >= zone["date"].min()]
    return {"lines": merged.reset_index().rename(columns={"index": "date"})
            .to_dict("records")}


def _auto_scatter(df: pd.DataFrame, location: str) -> dict:
    """Fare against distance, with the notified schedule overlaid."""
    sched = gazette.schedule()
    z = df[(df["item"] == "auto_ride") & (df["location"] == location)
           & df["distance_km"].notna()]
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
    payload = {"kind": "band", "window": flag["window"], "daily": _daily_band(g)}
    if item == "egg_table":
        payload["kind"] = "spread"
        payload.update(_egg_spread(df, location))
    elif item == "auto_ride":
        payload["kind"] = "scatter"
        payload.update(_auto_scatter(df, location))
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

    log("  detect")
    flags = detect.run_all(judged) if verbose else _quiet_detect(judged)

    log("  cases")
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

    # queue order: tier first, then how far outside the band it sits
    queue.sort(key=lambda f: (-f["tier"], -abs(f["observed"]["median"]
                                               / max(f["expected"]["rate"], 1e-9) - 1)))

    meta = {
        "data_through": str(obs["date"].max()),
        "data_from": str(obs["date"].min()),
        "observations": int(len(obs)),
        "locations_monitored": int(obs["location"].nunique()),
        "items_monitored": int(obs["item"].nunique()),
        "rejected_reports": int(reports.REJECTED.get("no_geotag_or_timestamp", 0)),
        "flags_total": len(all_flags),
        "flags_in_queue": len(queue),
        "flags_excluded_evidence_floor": len(all_flags) - len(queue),
        "model": model.metrics,
        "thresholds": detect.THRESHOLDS,
        "generaliser": gen,
        "tier_counts": {str(k): int(v) for k, v in
                        pd.Series([f["tier"] for f in queue]).value_counts().items()},
        "sources": sorted(obs["source"].unique().tolist()),
    }
    log(f"\n  {len(queue)} flag(s) in the inspection queue, "
        f"{len(all_flags) - len(queue)} excluded by the evidence floor")
    return {"queue": queue, "flags": all_flags, "cases": case_files,
            "charts": charts, "meta": meta, "model": model}


def _quiet_detect(judged: pd.DataFrame) -> list[dict]:
    import io
    import contextlib
    with contextlib.redirect_stdout(io.StringIO()):
        return detect.run_all(judged)


def main() -> None:
    print("building (offline; no network access)")
    obs = ingest()
    result = compute(obs)
    for name in ("queue", "flags", "cases", "charts", "meta"):
        _write(f"{name}.json", result[name])


if __name__ == "__main__":
    main()
