"""Field reports from the collection form (tier C).

Rows without a geotag or a timestamp are rejected outright. seller_id comes from
rounding the coordinates to a ~50m grid: we identify locations, never traders.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from pipeline.contracts import validate_observations
from pipeline.ingest._common import RAW, blank_frame, grid_seller_id

def _known_locations() -> dict[str, tuple[float, float]]:
    """Every place a report can be attributed to.

    The real market ids come from the Agmarknet adapter, so a commodity report
    lands on a market that actually exists in the panel. The zones below carry
    the egg and auto verticals, which have no mandi equivalent.
    """
    from pipeline.ingest.agmarknet_export import EXCLUDED_MARKETS, TOWNS

    places: dict[str, tuple[float, float]] = {}
    for town, coords in TOWNS.items():
        for kind in ("apmc", "sandhai"):
            key = f"{town}_{kind}"
            if key not in EXCLUDED_MARKETS:
                places[key] = coords
    places.update({
        "vellore_katpadi":      (12.9698, 79.1325),
        "vellore_bagayam":      (12.9060, 79.0930),
        "vellore_sathuvachari": (12.9340, 79.1560),
        "vellore_thorapadi":    (12.9010, 79.1420),
        "vellore_ranipet":      (12.9500, 79.3300),
    })
    return places


ITEM_LOCATIONS = _known_locations()

# Commodity reports belong at a market; egg and auto reports belong in a zone.
ZONE_LOCATIONS = {k: v for k, v in ITEM_LOCATIONS.items() if k.startswith("vellore_")}
MARKET_LOCATIONS = {k: v for k, v in ITEM_LOCATIONS.items() if not k.startswith("vellore_")}

REJECTED: dict[str, int] = {}


def fetch() -> None:
    raise NotImplementedError("Reports arrive as a form CSV in data/raw/reports/.")


def _nearest_location(lat: float, lng: float, item: str = "") -> str:
    """Attribute a geotag to the nearest place *of the right kind*.

    Without the item, an egg report near a mandi would be filed against that
    mandi, where the egg vertical has no reference rate at all.
    """
    pool = ZONE_LOCATIONS if item in {"egg_table", "auto_ride"} else MARKET_LOCATIONS
    pool = pool or ITEM_LOCATIONS
    return min(pool, key=lambda k: (pool[k][0] - lat) ** 2 + (pool[k][1] - lng) ** 2)


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
        "location": [_nearest_location(a, b, it) for a, b, it
                     in zip(lat, lng, raw["item"].str.strip())],
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
