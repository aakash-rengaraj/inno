"""Tamil Nadu autorickshaw fare — the reference rate for autos.

Two rates exist and conflating them was a real defect here. The **statutory**
rate (Rs 25 / 1.8 km, Rs 12 per km) was announced in August 2013 and has not been
revised in thirteen years. The **prevailing** rate (Rs 50 / 1.8 km, Rs 18 per km,
from 1 February 2025) was declared by the drivers' unions and is not a government
order, but it is what riders are actually quoted against.

We benchmark against the prevailing rate. Measured against the 2013 rate, a
present-day fare is roughly double it before anyone does anything wrong, and the
detectors would be reading thirteen years of inflation as manipulation.

The rate lives in data/raw/reference/tn_auto_fare.json, which is **committed
source material and must never be generated** -- its `citation` string is copied
verbatim into case files, so an invented string here becomes an invented citation
in a document that reads as an enforcement record.
"""
from __future__ import annotations

import json

import pandas as pd

from pipeline.contracts import validate_references
from pipeline.ingest._common import RAW

ZONES = ["vellore_katpadi", "vellore_bagayam", "vellore_sathuvachari", "vellore_thorapadi"]


def schedule() -> dict:
    """The benchmark block, flattened, with its citation attached."""
    doc = json.loads((RAW / "reference" / "tn_auto_fare.json").read_text())
    which = doc.get("benchmark", "prevailing")
    block = dict(doc[which])
    block["basis"] = which
    block["currency"] = doc.get("currency", "INR")
    block["caveat"] = doc.get("caveat", "")
    block["statutory_note"] = doc["statutory"]["citation"]
    return block


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
