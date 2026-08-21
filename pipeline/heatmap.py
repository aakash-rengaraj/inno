"""Field-report price deviation, binned to a fixed grid over Vellore district.

Two decisions worth stating, because the obvious version of this feature is
wrong in both:

**Colour is deviation, not report count.** A density map of citizen reports maps
where people have phones and civic energy, not where prices are manipulated --
and on screen a dark blob reads as an accusation. The cell value here is the
median gap between what reporters paid and the modelled band for that day, so a
zone with 400 reports at fair prices renders cold and a six-report cell paying
30% over renders hot. Count only drives opacity.

**Cells below the evidence floor are not drawn.** `cases.apply_evidence_floor`
keeps a finding out of the queue until three independent localities corroborate
it; a cell rendered from one walk-past would put on screen exactly the claim the
floor exists to withhold.

The cell is 150 m -- the same radius `generalise.py` merges reporting points at,
so one cell is approximately one locality and the map is drawn at the resolution
the evidence is actually counted at.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Fixed extent. The map does not pan and does not zoom: an enforcement map that
# can be scrolled off its own jurisdiction invites reading a neighbouring
# district's prices as this district's problem.
FRAME = {"lat_min": 12.885, "lat_max": 12.985,
         "lng_min": 79.070, "lng_max": 79.345}

CELL_M = 150.0
MIN_REPORTS = 1          # display only -- see the note above; the queue floor is 3
M_PER_DEG_LAT = 110_574.0
M_PER_DEG_LNG = 108_400.0   # at ~12.9 N


def _cell_size() -> tuple[float, float]:
    return CELL_M / M_PER_DEG_LAT, CELL_M / M_PER_DEG_LNG


def in_frame(lat: pd.Series, lng: pd.Series) -> pd.Series:
    return (lat.between(FRAME["lat_min"], FRAME["lat_max"])
            & lng.between(FRAME["lng_min"], FRAME["lng_max"]))


def places_in_frame() -> list[dict]:
    """Landmarks so the frame reads as a district and not an abstract grid."""
    from pipeline.ingest.reports import MARKET_LOCATIONS, ZONE_LOCATIONS

    def label(key: str) -> str:
        if key.endswith("_sandhai"):
            return key[: -len("_sandhai")].replace("_", " ").title()
        if key.endswith("_apmc"):
            return key[: -len("_apmc")].replace("_", " ").title()
        return key.replace("vellore_", "").replace("_", " ").title()

    out, seen = [], set()
    for kind, src in (("market", MARKET_LOCATIONS), ("zone", ZONE_LOCATIONS)):
        for key, (lat, lng) in sorted(src.items()):
            if not (FRAME["lat_min"] <= lat <= FRAME["lat_max"]
                    and FRAME["lng_min"] <= lng <= FRAME["lng_max"]):
                continue
            name = label(key)
            if name in seen:            # apmc and sandhai share a coordinate
                continue
            seen.add(name)
            out.append({"id": key, "label": name, "lat": lat, "lng": lng, "kind": kind})
    return out


def build(scored: pd.DataFrame, window_days: int | None = None) -> dict:
    """Grid the tier-C observations. `scored` is the output of attach_expectations."""
    df = scored[(scored["tier"] == "C") & scored["lat"].notna() & scored["lng"].notna()].copy()

    if window_days and not df.empty:
        cutoff = (pd.to_datetime(df["date"].max())
                  - pd.Timedelta(days=window_days)).strftime("%Y-%m-%d")
        df = df[df["date"] >= cutoff]

    outside = int((~in_frame(df["lat"], df["lng"])).sum())
    df = df[in_frame(df["lat"], df["lng"])]
    if df.empty:
        return {"frame": dict(FRAME), "cell_m": CELL_M, "min_reports": MIN_REPORTS,
                "cells": [], "items": [], "places": places_in_frame(),
                "outside_frame": outside, "totals": {}}

    # deviation from the middle of the modelled band, in band widths as well as
    # percent: a 10% gap means different things for eggs and for a 12 km fare.
    mid = df["expected_mid"].to_numpy(dtype=float)
    hi = df["expected_hi"].to_numpy(dtype=float)
    lo = df["expected_lo"].to_numpy(dtype=float)
    price = df["price"].to_numpy(dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        df["deviation"] = np.where(mid > 0, price / mid - 1.0, np.nan)
        width = np.maximum(hi - lo, 1e-9)
        df["band_gap"] = np.where(price > hi, (price - hi) / width,
                                  np.where(price < lo, (price - lo) / width, 0.0))
    df = df[df["deviation"].notna()]

    dlat, dlng = _cell_size()
    df["row"] = np.floor((df["lat"] - FRAME["lat_min"]) / dlat).astype(int)
    df["col"] = np.floor((df["lng"] - FRAME["lng_min"]) / dlng).astype(int)

    cells, suppressed = [], 0
    for (item, row, col), g in df.groupby(["item", "row", "col"], observed=True):
        n = len(g)
        if n < MIN_REPORTS:
            suppressed += 1
            continue
        cells.append({
            "item": str(item),
            "lat": round(FRAME["lat_min"] + (row + 0.5) * dlat, 6),
            "lng": round(FRAME["lng_min"] + (col + 0.5) * dlng, 6),
            "n": n,
            "localities": int(g["unit_id"].nunique()) if "unit_id" in g else 0,
            "deviation": round(float(g["deviation"].median()), 4),
            "band_gap": round(float(g["band_gap"].median()), 3),
            "above_band": int((g["price"] > g["expected_hi"]).sum()),
            "median_price": round(float(g["price"].median()), 2),
            "first": str(g["date"].min()),
            "last": str(g["date"].max()),
        })

    cells.sort(key=lambda c: -abs(c["deviation"]))
    items = sorted({c["item"] for c in cells})
    return {
        "frame": dict(FRAME),
        "cell_m": CELL_M,
        "min_reports": MIN_REPORTS,
        "cells": cells,
        "items": items,
        "places": places_in_frame(),
        "outside_frame": outside,
        "suppressed_cells": suppressed,
        "totals": {
            "reports": int(len(df)),
            "reports_shown": int(sum(c["n"] for c in cells)),
            "cells": len(cells),
        },
    }
