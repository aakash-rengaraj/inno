"""Ride-hailing fare estimates (tier B). Autos vertical."""
from __future__ import annotations

import json

import pandas as pd

from pipeline.contracts import validate_observations
from pipeline.ingest._common import RAW, blank_frame, pseudonym


def fetch() -> None:
    raise NotImplementedError("Estimates are committed to data/raw/ridehail/.")


def parse() -> pd.DataFrame:
    rows = []
    for path in sorted((RAW / "ridehail").glob("*.jsonl")):
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            e = json.loads(line)
            rows.append({
                "item": "auto_ride",
                "location": e["zone"],
                "lat": float(e["pickup"]["lat"]), "lng": float(e["pickup"]["lng"]),
                "date": e["captured_at"][:10],
                "price": float(e["fare_estimate"]),
                "unit": "per_ride",
                "seller_id": pseudonym("rh", e["platform"], e["zone"]),
                "source": "ridehail",
                "tier": "B",
                "distance_km": float(e["distance_km"]),
            })
    df = pd.DataFrame(rows)
    df = df.assign(**blank_frame(len(df)))
    df["distance_km"] = [r["distance_km"] for r in rows]
    return validate_observations(df, "ridehail")
