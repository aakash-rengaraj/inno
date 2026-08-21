"""Holds the computed state and recomputes it when the evidence set changes.

The band model is fitted once at startup and reused. A citizen report does not
change the Agmarknet backbone the band is fitted on, so refitting per report
would burn seconds to arrive at the same model.
"""
from __future__ import annotations

import threading
import time

import pandas as pd

from pipeline.build import compute, parse_sources
from pipeline.ingest import reports as reports_ingest
from pipeline.model import fit_band

PUBLIC_META_FIELDS = [
    "data_from", "data_through", "observations", "locations_monitored",
    "items_monitored", "flags_in_queue", "flags_excluded_evidence_floor", "sources",
]


def _attach_citizen_reports(result: dict, submitted: list[dict]) -> None:
    """Name, on each finding, the citizen reports that are part of its evidence.

    Reports were already counted -- they enter as tier C observations and show up
    in `observed.n` -- but nothing said *which* reports, so a person who had just
    filed one had no way to see it land. The number went up by one somewhere.

    Matched on **item and market**, with `in_window` recorded separately rather
    than used as a filter. Filtering on the window looked stricter and was in
    practice useless: a finding's window closes on the last day the pattern was
    observed, so a report filed today falls after nearly every one of them and
    the honest answer became "no citizen reports" for a report that plainly
    concerned that market.

    So both facts are carried. The report is evidence about this market and this
    item -- that is true and it is what a reporter wants to see. Whether it falls
    inside the specific run the detector measured is a different question, and
    the flag marks it rather than hiding it.

    It attaches references only, never notes or coordinates -- the console has a
    separate screen for the report itself, and a case file must not start
    carrying free text somebody typed into a form.
    """
    # `attributed_to` is derived, not stored: the reports table keeps raw
    # coordinates, and the market is worked out on read. Reading the key off the
    # row returned None for every report, so this matched nothing at all and
    # reported it as "no citizen reports" rather than as a failure.
    from pipeline.ingest.reports import _nearest_location

    by_flag: dict[str, list[dict]] = {}
    for r in submitted:
        item = r.get("item")
        day = str(r.get("submitted_at", ""))[:10]
        loc = r.get("attributed_to")
        if loc is None and r.get("lat") is not None:
            try:
                loc = _nearest_location(r["lat"], r["lng"], item)
            except Exception:
                loc = None
        if not (loc and item and day):
            continue
        for flag in result.get("flags", []):
            if flag["item"] != item or flag["location"] != loc:
                continue
            by_flag.setdefault(flag["flag_id"], []).append({
                "reference": r.get("reference"),
                "submitted_at": r.get("submitted_at"),
                "price_inr": r.get("price_inr"),
                "in_window": flag["window"]["start"] <= day <= flag["window"]["end"],
            })

    for coll in (result.get("flags", []), result.get("queue", [])):
        for flag in coll:
            got = by_flag.get(flag["flag_id"], [])
            got = sorted(got, key=lambda x: x["submitted_at"] or "", reverse=True)
            flag["citizen_reports"] = got
            flag["citizen_report_count"] = len(got)
            flag["citizen_reports_in_window"] = sum(1 for x in got if x["in_window"])


class Engine:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pending = threading.Event()
        self._worker: threading.Thread | None = None
        self.state = "idle"          # idle | recomputing
        self.base: pd.DataFrame | None = None
        self.model = None
        self.artifacts: dict = {}
        self.last_recompute: dict = {}

    # --- background recompute ----------------------------------------------

    def request_recompute(self, fetch_reports) -> None:
        """Schedule a recompute without making the caller wait for it.

        A recompute takes seconds over a 200k-row panel, and a citizen
        submitting a price should not sit through it. Requests coalesce: five
        reports arriving together produce one recompute, not five.
        """
        self._pending.set()
        if self._worker is not None and self._worker.is_alive():
            return
        self._worker = threading.Thread(target=self._drain, args=(fetch_reports,),
                                        daemon=True)
        self._worker.start()

    def _drain(self, fetch_reports) -> None:
        while self._pending.is_set():
            self._pending.clear()
            self.state = "recomputing"
            try:
                self.recompute(fetch_reports())
            except Exception as exc:               # a bad report must not kill the loop
                print(f"  recompute failed: {exc}")
            finally:
                self.state = "idle"

    @property
    def busy(self) -> bool:
        return self.state == "recomputing" or self._pending.is_set()

    # --- lifecycle ---------------------------------------------------------

    def start(self, fetch_reports=None) -> None:
        """Fit the band and compute the first set of artifacts.

        `fetch_reports` must be supplied or every citizen report already on file
        is dropped. This used to call `recompute([])`, so a restart silently
        emptied the evidence: reports stayed in the database, disappeared from
        the analysis, and came back only when the next person happened to submit
        one and triggered a recompute. On a server that restarts after every
        deploy, that is most of the time.
        """
        t0 = time.perf_counter()
        self.base = parse_sources(verbose=False)
        self.model = fit_band(self.base)
        print(f"  band model fitted on {self.model.metrics['n_train']} rows "
              f"(coverage {self.model.metrics['band_coverage']})")

        stored = []
        if fetch_reports is not None:
            try:
                stored = fetch_reports()
            except Exception as exc:
                print(f"  WARNING: could not load stored reports: {exc}")
        self.recompute(stored)
        print(f"  engine ready in {time.perf_counter() - t0:.1f}s "
              f"({len(stored)} citizen report(s) loaded)")

    # --- recompute ---------------------------------------------------------

    def recompute(self, submitted: list[dict]) -> dict:
        """Rebuild every artifact from data/raw plus the submitted reports."""
        with self._lock:
            t0 = time.perf_counter()
            obs = self.base
            live = self._reports_to_observations(submitted)
            if live is not None and len(live):
                obs = pd.concat([self.base, live], ignore_index=True)
            result = compute(obs, model=self.model, verbose=False)
            _attach_citizen_reports(result, submitted)
            self.artifacts = result
            self.last_recompute = {
                "at": pd.Timestamp.utcnow().isoformat(timespec="seconds"),
                "seconds": round(time.perf_counter() - t0, 2),
                "live_reports_included": 0 if live is None else int(len(live)),
                "observations": int(len(obs)),
                "flags_in_queue": len(result["queue"]),
            }
            return self.last_recompute

    def _reports_to_observations(self, submitted: list[dict]) -> pd.DataFrame | None:
        if not submitted:
            return None
        raw = pd.DataFrame([{
            "submitted_at": r["submitted_at"], "lat": r["lat"], "lng": r["lng"],
            "item": r["item"], "price_inr": r["price_inr"], "unit": r["unit"],
            "distance_km": r["distance_km"], "note": r.get("note", ""),
        } for r in submitted])
        # same normalisation the committed CSV goes through
        return reports_ingest.normalise(raw)

    # --- views -------------------------------------------------------------

    def public_meta(self) -> dict:
        """Aggregate counts only. No thresholds, no model internals, no flags.

        Also carries the places and items a citizen may report against, so the
        public form is driven by the data rather than a hardcoded list that
        silently drifts out of step with the ingest.
        """
        meta = self.artifacts.get("meta", {})
        out = {k: meta[k] for k in PUBLIC_META_FIELDS if k in meta}
        out["report_places"] = self.report_places()
        out["report_items"] = self.report_items(meta)
        return out

    def report_places(self) -> list[dict]:
        from pipeline.ingest.reports import MARKET_LOCATIONS, ZONE_LOCATIONS

        def label(key: str) -> str:
            """Market ids are <town>_<kind>; zone ids are vellore_<zone>.

            Stripping the "vellore_" prefix first turns `vellore_apmc` into
            "Apmc" and loses the town, so the suffix is taken off first and the
            prefix only for zones.
            """
            if key.endswith("_sandhai"):
                town = key[: -len("_sandhai")].replace("_", " ").title()
                return f"{town} (Uzhavar Sandhai)"
            if key.endswith("_apmc"):
                town = key[: -len("_apmc")].replace("_", " ").title()
                return f"{town} (APMC)"
            return key.replace("vellore_", "").replace("_", " ").title()

        places = [{"id": k, "label": label(k), "lat": v[0], "lng": v[1], "kind": "market"}
                  for k, v in sorted(MARKET_LOCATIONS.items())]
        places += [{"id": k, "label": label(k), "lat": v[0], "lng": v[1], "kind": "zone"}
                   for k, v in sorted(ZONE_LOCATIONS.items())]
        return places

    def report_items(self, meta: dict) -> list[dict]:
        """Items a citizen can report. Commodities are the ones actually present
        in the panel, so a report always has something to be compared against."""
        labels = meta.get("item_labels", {})
        present = set()
        if self.base is not None:
            present = set(self.base.loc[self.base["source"] == "agmarknet", "item"].unique())
        wanted = [i for i in ("tomato", "onion", "potato", "brinjal", "carrot")
                  if i in present]
        items = [{"id": i, "label": labels.get(i, i.title()),
                  "unit": "per_kg", "kind": "market"} for i in wanted]
        items.append({"id": "egg_table", "label": "Table eggs",
                      "unit": "per_piece", "kind": "zone"})
        items.append({"id": "auto_ride", "label": "Autorickshaw fare",
                      "unit": "per_ride", "kind": "zone"})
        return items


ENGINE = Engine()
