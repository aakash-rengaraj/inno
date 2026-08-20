"""q-commerce catalogue snapshots (tier B).

fetch(): Playwright, set the pincode/location cookie once, reuse the context —
catalogue requests return national pricing until a location is set.
"""
from __future__ import annotations

import json

import pandas as pd

from pipeline.contracts import validate_observations
from pipeline.ingest._common import RAW, blank_frame, pseudonym

PACK_SIZES = {"6 pcs": 6, "12 pcs": 12, "30 pcs": 30}


def fetch() -> None:
    raise NotImplementedError("Snapshots are committed to data/raw/qcommerce/.")


def parse() -> pd.DataFrame:
    rows = []
    for path in sorted((RAW / "qcommerce").glob("*.jsonl")):
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            snap = json.loads(line)
            date = snap["captured_at"][:10]
            for r in snap["results"]:
                if not r.get("in_stock", True):
                    continue
                pieces = PACK_SIZES.get(r["pack"])
                assert pieces, f"unknown pack size {r['pack']!r} in {path.name}"
                rows.append({
                    "item": "egg_table",
                    "location": snap["zone"],
                    "lat": float(snap["lat"]), "lng": float(snap["lng"]),
                    "date": date,
                    "price": float(r["price"]) / pieces,   # normalised at ingest
                    "unit": "per_piece",
                    "seller_id": pseudonym("qc", snap["platform"], snap["zone"]),
                    "source": "qcommerce",
                    "tier": "B",
                })
    df = pd.DataFrame(rows)
    # one price per (seller, zone, day): pack sizes are the same listing
    df = (df.groupby(["item", "location", "lat", "lng", "date", "unit", "seller_id",
                      "source", "tier"], as_index=False)["price"].median())
    df = df.assign(**blank_frame(len(df)))
    return validate_observations(df, "qcommerce")
