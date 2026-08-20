"""Field reports from the collection form (tier C).

Rows without a geotag or a timestamp are rejected outright. seller_id comes from
rounding the coordinates to a ~50m grid: we identify locations, never traders.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from pipeline.contracts import validate_observations
from pipeline.ingest._common import RAW, blank_frame, grid_seller_id

ITEM_LOCATIONS = {
    "vellore_market":      (12.9165, 79.1325),
    "vellore_gudiyatham":  (12.9450, 78.8700),
    "vellore_vaniyambadi": (12.6820, 78.6200),
    "vellore_arakkonam":   (13.0830, 79.6700),
    "vellore_katpadi":     (12.9698, 79.1325),
    "vellore_bagayam":     (12.9060, 79.0930),
    "vellore_sathuvachari": (12.9340, 79.1560),
    "vellore_thorapadi":   (12.9010, 79.1420),
    "vellore_ranipet":     (12.9500, 79.3300),
}

REJECTED: dict[str, int] = {}


def fetch() -> None:
    raise NotImplementedError("Reports arrive as a form CSV in data/raw/reports/.")


def _nearest_location(lat: float, lng: float) -> str:
    return min(ITEM_LOCATIONS, key=lambda k: (ITEM_LOCATIONS[k][0] - lat) ** 2
               + (ITEM_LOCATIONS[k][1] - lng) ** 2)


def parse() -> pd.DataFrame:
    raw = pd.read_csv(RAW / "reports" / "field_reports.csv")
    before = len(raw)
    df = normalise(raw)
    print(f"    reports: kept {len(df)}/{before}, "
          f"rejected {REJECTED['no_geotag_or_timestamp']} for missing geotag or timestamp")
    return df


def normalise(raw: pd.DataFrame) -> pd.DataFrame:
    """Form rows -> Observation schema.

    Used by `parse()` for the committed CSV and by the API for live submissions,
    so a report is treated identically however it arrives.
    """
    ok = raw["lat"].notna() & raw["lng"].notna() & raw["submitted_at"].notna()
    ok &= raw["price_inr"].notna() & (raw["price_inr"] > 0)
    REJECTED["no_geotag_or_timestamp"] = int((~ok).sum())
    raw = raw[ok].copy()

    n = len(raw)
    lat = raw["lat"].astype(float).to_numpy()
    lng = raw["lng"].astype(float).to_numpy()
    df = pd.DataFrame({
        "item": raw["item"].str.strip(),
        "location": [_nearest_location(a, b) for a, b in zip(lat, lng)],
        "lat": lat, "lng": lng,
        "date": raw["submitted_at"].str.slice(0, 10),
        "price": raw["price_inr"].astype(float),
        "unit": raw["unit"].str.strip(),
        "seller_id": [grid_seller_id(a, b) for a, b in zip(lat, lng)],
        "source": "report",
        "tier": "C",
        **blank_frame(n),
    })
    df["distance_km"] = pd.to_numeric(raw["distance_km"], errors="coerce").to_numpy()
    df.loc[~df["unit"].isin({"per_km", "per_ride"}), "distance_km"] = np.nan
    return validate_observations(df, "reports")
