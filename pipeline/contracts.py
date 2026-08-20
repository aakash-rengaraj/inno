"""Frozen data contracts. Everything downstream depends on these.

Do not change after hour 4 of day 1. See SPEC.md section 4.
"""
from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd
from pipeline import paths

# --- 4.1 Observation -------------------------------------------------------

OBSERVATION_COLUMNS: dict[str, str] = {
    "item": "string",        # canonical id, e.g. "egg_table", "tomato", "auto_ride"
    "location": "string",    # canonical market/zone id, e.g. "vellore_katpadi"
    "lat": "float64",
    "lng": "float64",
    "date": "string",        # YYYY-MM-DD
    "price": "float64",      # INR, already unit-normalised
    "unit": "string",
    "seller_id": "string",   # pseudonymous; NEVER a real business name
    "source": "string",
    "tier": "string",        # A authoritative | B scraped commercial | C user report
    "arrivals": "float64",   # supply proxy; NaN where not applicable
    "distance_km": "float64",  # autos only; NaN otherwise
}

UNITS = {"per_piece", "per_kg", "per_km", "per_ride"}
SOURCES = {"agmarknet", "necc", "qcommerce", "ridehail", "report"}
TIERS = {"A", "B", "C"}
REF_SOURCES = {"necc", "tn_gazette", "agmarknet_wholesale"}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ID_RE = re.compile(r"^[a-z0-9_]+$")

OBSERVATIONS_PATH = str(paths.OBSERVATIONS)


def empty_observations() -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype=t) for c, t in OBSERVATION_COLUMNS.items()})


def validate_observations(df: pd.DataFrame, source_name: str = "<unknown>") -> pd.DataFrame:
    """Assert the Observation contract and return the frame in canonical column order."""
    where = f"[{source_name}]"
    missing = set(OBSERVATION_COLUMNS) - set(df.columns)
    assert not missing, f"{where} missing observation columns: {sorted(missing)}"
    extra = set(df.columns) - set(OBSERVATION_COLUMNS)
    assert not extra, f"{where} unexpected columns: {sorted(extra)}"

    df = df[list(OBSERVATION_COLUMNS)].copy()
    for col, dtype in OBSERVATION_COLUMNS.items():
        df[col] = df[col].astype(dtype)

    if df.empty:
        return df

    bad_unit = set(df["unit"]) - UNITS
    assert not bad_unit, f"{where} unknown unit(s): {sorted(bad_unit)}"
    bad_source = set(df["source"]) - SOURCES
    assert not bad_source, f"{where} unknown source(s): {sorted(bad_source)}"
    bad_tier = set(df["tier"]) - TIERS
    assert not bad_tier, f"{where} unknown tier(s): {sorted(bad_tier)}"

    bad_date = df.loc[~df["date"].str.match(_DATE_RE), "date"].unique()
    assert len(bad_date) == 0, f"{where} dates not YYYY-MM-DD: {list(bad_date)[:5]}"

    for col in ("item", "location", "seller_id"):
        bad = df.loc[~df[col].str.match(_ID_RE), col].unique()
        assert len(bad) == 0, f"{where} {col} must be lowercase snake ids: {list(bad)[:5]}"

    assert df["price"].notna().all(), f"{where} null prices"
    assert (df["price"] > 0).all(), f"{where} non-positive prices"
    assert df["lat"].between(-90, 90).all(), f"{where} lat out of range"
    assert df["lng"].between(-180, 180).all(), f"{where} lng out of range"

    # Autos carry a distance; nothing else does.
    ride = df["unit"].isin({"per_km", "per_ride"})
    assert df.loc[~ride, "distance_km"].isna().all(), f"{where} distance_km set on non-auto rows"
    return df


# --- 4.2 Reference rate ----------------------------------------------------

REFERENCE_COLUMNS: dict[str, str] = {
    "item": "string",
    "location": "string",
    "date": "string",
    "rate": "float64",
    "unit": "string",
    "source": "string",     # necc | tn_gazette | agmarknet_wholesale
    "citation": "string",   # appears verbatim in the case file
}


def empty_references() -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype=t) for c, t in REFERENCE_COLUMNS.items()})


def validate_references(df: pd.DataFrame, source_name: str = "<unknown>") -> pd.DataFrame:
    where = f"[{source_name}]"
    missing = set(REFERENCE_COLUMNS) - set(df.columns)
    assert not missing, f"{where} missing reference columns: {sorted(missing)}"
    df = df[list(REFERENCE_COLUMNS)].copy()
    for col, dtype in REFERENCE_COLUMNS.items():
        df[col] = df[col].astype(dtype)
    if df.empty:
        return df

    bad_source = set(df["source"]) - REF_SOURCES
    assert not bad_source, f"{where} unknown reference source(s): {sorted(bad_source)}"
    bad_unit = set(df["unit"]) - UNITS
    assert not bad_unit, f"{where} unknown unit(s): {sorted(bad_unit)}"
    bad_date = df.loc[~df["date"].str.match(_DATE_RE), "date"].unique()
    assert len(bad_date) == 0, f"{where} dates not YYYY-MM-DD: {list(bad_date)[:5]}"
    assert (df["rate"] > 0).all(), f"{where} non-positive reference rate"
    # A case file without a citable source is worthless.
    blank = df["citation"].isna() | (df["citation"].str.strip() == "")
    assert not blank.any(), f"{where} {int(blank.sum())} reference rows without a citation"
    return df


# --- 4.3 Flag --------------------------------------------------------------

DETECTORS = {"variance_collapse", "cost_correlation", "persistence", "quantisation"}

FLAG_KEYS = {
    "flag_id", "tier", "item", "location", "window", "detector",
    "statistic", "expected", "observed", "residual_sd", "peers_in_band", "narrative",
}


def make_flag(
    *,
    flag_id: str,
    tier: int,
    item: str,
    location: str,
    window: dict[str, str],
    detector: str,
    statistic: dict[str, Any],
    expected: dict[str, Any],
    observed: dict[str, Any],
    residual_sd: float,
    peers_in_band: list[str],
    narrative: str,
) -> dict[str, Any]:
    """Build a Flag dict and assert the contract at construction time."""
    flag = {
        "flag_id": flag_id,
        "tier": int(tier),
        "item": item,
        "location": location,
        "window": window,
        "detector": detector,
        "statistic": statistic,
        "expected": expected,
        "observed": observed,
        "residual_sd": float(residual_sd),
        "peers_in_band": list(peers_in_band),
        "narrative": narrative,
    }
    return validate_flag(flag)


def validate_flag(flag: dict[str, Any]) -> dict[str, Any]:
    assert set(flag) == FLAG_KEYS, f"flag key mismatch: {sorted(set(flag) ^ FLAG_KEYS)}"
    assert re.match(r"^FLG-\d{4}$", flag["flag_id"]), f"bad flag_id {flag['flag_id']!r}"
    assert flag["tier"] in (1, 2, 3), f"bad tier {flag['tier']}"
    assert flag["detector"] in DETECTORS, f"unknown detector {flag['detector']!r}"

    assert set(flag["window"]) == {"start", "end"}, "window needs start and end"
    assert flag["window"]["start"] <= flag["window"]["end"], "window ends before it starts"

    # a detector may carry extra supporting numbers, but never fewer than these
    assert {"name", "value", "threshold"} <= set(flag["statistic"]), "statistic shape"
    assert set(flag["expected"]) == {"rate", "band", "unit"}, "expected shape"
    lo, hi = flag["expected"]["band"]
    assert lo <= hi, "expected band inverted"
    assert flag["expected"]["unit"] in UNITS, f"bad unit {flag['expected']['unit']!r}"

    assert set(flag["observed"]) == {"median", "n", "tier_mix"}, "observed shape"
    assert flag["observed"]["n"] > 0, "flag with no observations"
    assert set(flag["observed"]["tier_mix"]) <= TIERS, "tier_mix has unknown tiers"
    assert sum(flag["observed"]["tier_mix"].values()) == flag["observed"]["n"], \
        "tier_mix does not sum to n"

    assert flag["narrative"].strip(), "flag without a narrative"
    # Language discipline: we flag for investigation, we never assert proof.
    lowered = flag["narrative"].lower()
    for banned in ("proven", "proves", "cartel", "guilty", "collusion is"):
        assert banned not in lowered, f"narrative asserts proof: {banned!r}"
    return flag


def flag_id(n: int) -> str:
    return f"FLG-{n:04d}"


def json_safe(obj: Any) -> Any:
    """Recursively convert numpy scalars so json.dump does not choke."""
    if isinstance(obj, dict):
        return {k: json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return None if np.isnan(obj) else round(float(obj), 4)
    if isinstance(obj, float):
        return None if pd.isna(obj) else round(obj, 4)
    if obj is pd.NA:
        return None
    return obj
