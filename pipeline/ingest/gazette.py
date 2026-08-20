"""TN gazetted autorickshaw fare schedule — the reference rate for autos."""
from __future__ import annotations

import json

import pandas as pd

from pipeline.contracts import validate_references
from pipeline.ingest._common import RAW

ZONES = ["vellore_katpadi", "vellore_bagayam", "vellore_sathuvachari", "vellore_thorapadi"]


def schedule() -> dict:
    return json.loads((RAW / "reference" / "tn_auto_fare.json").read_text())


def fare_for(km: float, sched: dict | None = None) -> float:
    """Notified fare for a ride of `km`, per the gazette."""
    s = sched or schedule()
    extra = max(0.0, km - s["minimum_fare_included_km"])
    return s["minimum_fare"] + extra * s["per_km_after"]


def references(dates: list[str]) -> pd.DataFrame:
    """The gazette is a per-km schedule; it does not change day to day."""
    s = schedule()
    rows = []
    for zone in ZONES:
        rows.append(pd.DataFrame({
            "item": "auto_ride", "location": zone, "date": dates,
            "rate": s["per_km_after"], "unit": "per_km", "source": "tn_gazette",
            "citation": s["citation"],
        }))
    return validate_references(pd.concat(rows, ignore_index=True), "gazette")
