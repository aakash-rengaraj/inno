"""Shared ingest helpers. Unit normalisation and pseudonymisation live here."""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
from pipeline import paths

RAW = paths.RAW

# ~50m grid. Reports identify *locations*, never named traders.
GRID_DEG = 0.00045


def pseudonym(prefix: str, *parts: str) -> str:
    """Stable pseudonymous seller id. A real business name must never survive this."""
    digest = hashlib.sha1("|".join(parts).encode()).hexdigest()[:8]
    return f"{prefix}_{digest}"


def grid_seller_id(lat: float, lng: float) -> str:
    return f"grid_{int(round(lat / GRID_DEG))}_{int(round(lng / GRID_DEG))}"


def blank_frame(n: int) -> dict[str, object]:
    """Column defaults so every parser returns the full Observation schema."""
    return {"arrivals": np.full(n, np.nan), "distance_km": np.full(n, np.nan)}


def quintal_to_kg(price_per_quintal: pd.Series) -> pd.Series:
    return price_per_quintal.astype(float) / 100.0


def per_hundred_to_each(rate_per_100: pd.Series) -> pd.Series:
    return rate_per_100.astype(float) / 100.0


def read_jsonl(path: Path) -> pd.DataFrame:
    return pd.read_json(path, lines=True)
