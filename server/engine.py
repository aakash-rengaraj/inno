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


class Engine:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.base: pd.DataFrame | None = None
        self.model = None
        self.artifacts: dict = {}
        self.last_recompute: dict = {}

    # --- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        t0 = time.perf_counter()
        self.base = parse_sources(verbose=False)
        self.model = fit_band(self.base)
        print(f"  band model fitted on {self.model.metrics['n_train']} rows "
              f"(coverage {self.model.metrics['band_coverage']})")
        self.recompute([])
        print(f"  engine ready in {time.perf_counter() - t0:.1f}s")

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
            base = key.replace("vellore_", "").replace("_apmc", "").replace("_sandhai", "")
            name = base.replace("_", " ").title()
            if key.endswith("_sandhai"):
                return f"{name} (Uzhavar Sandhai)"
            if key.endswith("_apmc"):
                return f"{name} (APMC)"
            return name

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
