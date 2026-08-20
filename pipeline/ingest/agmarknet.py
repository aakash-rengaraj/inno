"""Agmarknet mandi prices — the tier-A backbone, and the only source with history.

fetch(): agmarknet.gov.in has been rebuilt as a SPA whose data API sits behind a
captcha endpoint. Live fetching is therefore a manual step; see data/raw/README.md.
Scrape once, commit the CSVs, never call it again during the demo.
"""
from __future__ import annotations

import pandas as pd

from pipeline.contracts import validate_observations
from pipeline.ingest._common import RAW, blank_frame, pseudonym, quintal_to_kg

ITEMS = {"Tomato": "tomato", "Onion": "onion"}

MANDI_COORDS = {
    "vellore_market":      (12.9165, 79.1325),
    "vellore_gudiyatham":  (12.9450, 78.8700),
    "vellore_vaniyambadi": (12.6820, 78.6200),
    "vellore_arakkonam":   (13.0830, 79.6700),
}


def fetch() -> None:
    raise NotImplementedError(
        "Agmarknet is scraped offline and committed to data/raw/agmarknet/. "
        "The demo path must never touch the network."
    )


def parse() -> pd.DataFrame:
    frames = []
    for path in sorted((RAW / "agmarknet").glob("agmarknet_*.csv")):
        raw = pd.read_csv(path)
        n = len(raw)
        market = raw["Market Name"].str.strip()
        coords = market.map(MANDI_COORDS)
        assert coords.notna().all(), f"unmapped mandi in {path.name}"

        df = pd.DataFrame({
            "item": raw["Commodity"].str.strip().map(ITEMS),
            "location": market,
            "lat": coords.map(lambda c: c[0]),
            "lng": coords.map(lambda c: c[1]),
            "date": pd.to_datetime(raw["Price Date"], format="%d %b %Y").dt.strftime("%Y-%m-%d"),
            # normalise at ingest, never downstream
            "price": quintal_to_kg(raw["Modal Price (Rs./Quintal)"]),
            "unit": "per_kg",
            "seller_id": [pseudonym("mandi", m) for m in market],
            "source": "agmarknet",
            "tier": "A",
            **blank_frame(n),
        })
        # arrivals are load-bearing: without them we cannot separate scarcity from
        # manipulation, and the whole tier-2 argument collapses.
        df["arrivals"] = raw["Arrivals (Tonnes)"].astype(float)
        assert df["item"].notna().all(), f"unmapped commodity in {path.name}"
        frames.append(df)

    out = pd.concat(frames, ignore_index=True)
    return validate_observations(out, "agmarknet")


def references(obs: pd.DataFrame) -> pd.DataFrame:
    """Wholesale modal price is the cost reference for the retail commodity market.

    Each mandi's own modal price is the reference for retail prices in that town.
    """
    from pipeline.contracts import validate_references

    src = obs[(obs["source"] == "agmarknet")]
    refs = pd.DataFrame({
        "item": src["item"],
        "location": src["location"],
        "date": src["date"],
        "rate": src["price"],
        "unit": src["unit"],
        "source": "agmarknet_wholesale",
        "citation": ("Agmarknet daily mandi report — Directorate of Marketing & Inspection, "
                     "modal wholesale price, Vellore district"),
    }).reset_index(drop=True)
    return validate_references(refs, "agmarknet_wholesale")
