"""Schema assertions. Deliberately not a test suite — these guard the frozen
contracts in section 4 and nothing else.

    python -m pipeline.test_contracts
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from pipeline.contracts import (
    flag_id, make_flag, validate_flag, validate_observations, validate_references,
)

OBS = pd.DataFrame([
    dict(item="auto_ride", location="vellore_katpadi", lat=12.97, lng=79.13,
         date="2026-08-10", price=85.0, unit="per_ride", seller_id="grid_1297_7913",
         source="ridehail", tier="B", arrivals=np.nan, distance_km=2.4),
    dict(item="tomato", location="vellore_market", lat=12.92, lng=79.13,
         date="2026-08-10", price=42.0, unit="per_kg", seller_id="agmk_vellore",
         source="agmarknet", tier="A", arrivals=118.0, distance_km=np.nan),
])

REFS = pd.DataFrame([
    dict(item="auto_ride", location="vellore_katpadi", date="2026-08-10", rate=33.5,
         unit="per_ride", source="tn_gazette",
         citation="TN autorickshaw fare in force from 1 February 2025 (union-declared)"),
])

FLAG = dict(
    flag_id=flag_id(7), tier=3, item="auto_ride", location="vellore_katpadi",
    window={"start": "2026-06-01", "end": "2026-08-10"}, detector="quantisation",
    statistic={"name": "modal_mass_at_round_values", "value": 0.87, "threshold": 0.60},
    expected={"rate": 33.5, "band": [28.0, 39.0], "unit": "per_ride"},
    observed={"median": 85.0, "n": 42, "tier_mix": {"B": 18, "C": 24}},
    residual_sd=6.4, peers_in_band=["vellore_bagayam"],
    narrative="Quoted fares cluster at round values with weak distance sensitivity.",
)


def _rejects(label, fn) -> None:
    try:
        fn()
    except AssertionError:
        print(f"  rejects {label}")
    else:
        raise SystemExit(f"FAILED — {label} was accepted")


def main() -> None:
    obs = validate_observations(OBS, "test")
    refs = validate_references(REFS, "test")
    flag = make_flag(**FLAG)
    print(f"accepts valid observation/reference/flag ({flag['flag_id']})")

    _rejects("unknown unit", lambda: validate_observations(OBS.assign(unit="per_dozen"), "t"))
    _rejects("non-ISO date", lambda: validate_observations(OBS.assign(date="10/08/2026"), "t"))
    _rejects("named seller", lambda: validate_observations(
        OBS.assign(seller_id="Raja Auto Stand"), "t"))
    _rejects("negative price", lambda: validate_observations(OBS.assign(price=-1.0), "t"))
    _rejects("distance on a non-auto row", lambda: validate_observations(
        OBS.assign(distance_km=3.0), "t"))
    _rejects("reference without citation", lambda: validate_references(
        REFS.assign(citation="  "), "t"))
    _rejects("tier_mix not summing to n", lambda: validate_flag(
        {**flag, "observed": {**flag["observed"], "n": 43}}))
    _rejects("inverted window", lambda: validate_flag(
        {**flag, "window": {"start": "2026-08-10", "end": "2026-06-01"}}))
    _rejects("unknown detector", lambda: validate_flag({**flag, "detector": "detect_cartel"}))
    _rejects("narrative asserting proof", lambda: validate_flag(
        {**flag, "narrative": "This proves a cartel operated in Katpadi."}))

    assert len(obs) == 2 and len(refs) == 1
    print("all schema assertions hold")


if __name__ == "__main__":
    main()
