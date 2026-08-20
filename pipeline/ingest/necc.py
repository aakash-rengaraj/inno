"""NECC declared daily egg rate — authoritative reference for the egg vertical."""
from __future__ import annotations

import pandas as pd

from pipeline.contracts import validate_observations, validate_references
from pipeline.ingest._common import RAW, blank_frame, per_hundred_to_each

CITATION = "National Egg Coordination Committee — declared daily egg rate, Chennai zone"
ZONES = {
    "vellore_katpadi":      (12.9698, 79.1325),
    "vellore_bagayam":      (12.9060, 79.0930),
    "vellore_sathuvachari": (12.9340, 79.1560),
    "vellore_thorapadi":    (12.9010, 79.1420),
}


def fetch() -> None:
    raise NotImplementedError("NECC rates are committed to data/raw/necc/.")


def _raw() -> pd.DataFrame:
    raw = pd.read_csv(RAW / "necc" / "necc_declared_rates.csv")
    raw["date"] = pd.to_datetime(raw["Date"], format="%d-%m-%Y").dt.strftime("%Y-%m-%d")
    raw["rate"] = per_hundred_to_each(raw["Rate (Rs./100 eggs)"])
    return raw


def parse() -> pd.DataFrame:
    """The declared rate, carried as a tier-A observation so charts can draw it."""
    raw = _raw()
    lat, lng = ZONES["vellore_katpadi"]
    n = len(raw)
    df = pd.DataFrame({
        "item": "egg_table",
        "location": "vellore_declared",
        "lat": lat, "lng": lng,
        "date": raw["date"],
        "price": raw["rate"],
        "unit": "per_piece",
        "seller_id": "necc_declared",
        "source": "necc",
        "tier": "A",
        **blank_frame(n),
    })
    return validate_observations(df, "necc")


def references() -> pd.DataFrame:
    """The declared rate applies to every zone in the district."""
    raw = _raw()
    rows = []
    for zone in ZONES:
        rows.append(pd.DataFrame({
            "item": "egg_table", "location": zone, "date": raw["date"],
            "rate": raw["rate"], "unit": "per_piece", "source": "necc",
            "citation": CITATION,
        }))
    return validate_references(pd.concat(rows, ignore_index=True), "necc")
