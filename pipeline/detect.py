"""The four detectors.

Every flag must be reconstructible from the data. There is no black-box
classifier anywhere in this pipeline — every accusation gets explained on stage.

Governing idea, which all four implement a version of:
    Competitive prices track costs. Collusive prices track each other.
"""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

from pipeline.cases import narrate
from pipeline.contracts import flag_id, make_flag
from pipeline.expectations import comparable_price

# Tuned live while building the demo. One-line changes, by design.
THRESHOLDS = {
    "variance_collapse": {"cv_max": 0.030, "min_days": 14, "min_sellers": 3,
                          "min_out_of_band_share": 0.5},
    "cost_correlation": {"peer_min": 0.55, "cost_max": 0.30, "gap_min": 0.40,
                         "window": 21, "min_days": 30},
    "persistence": {"residual_min": 1.5, "min_consecutive_days": 10},
    "quantisation": {"round_mass_min": 0.60, "r2_max": 0.35, "min_obs": 30,
                     "round_to": 10, "roll_days": 14, "min_days": 21},
}

# Independence is counted in localities, not grid cells — see pipeline/generalise.py.
# At grid resolution one reporter walking 100m becomes two "independent sellers".
MIN_SELLERS_FOR_TIER_3 = 3

# a peer location is "in-band" if its median residual is within this many
# half-band units of the middle of its own expected range
PEER_IN_BAND_RESIDUAL = 1.0


def _counter() -> "itertools.count":
    return itertools.count(1)


def _emit(ids: "itertools.count", **kw) -> dict:
    """Assign the id, render the narrative from the template, then validate."""
    kw["flag_id"] = flag_id(next(ids))
    kw["narrative"] = narrate(kw)
    return make_flag(**kw)


def _tier_mix(g: pd.DataFrame) -> dict[str, int]:
    return {k: int(v) for k, v in g["tier"].value_counts().items()}


def _window(g: pd.DataFrame) -> dict[str, str]:
    return {"start": str(g["date"].min()), "end": str(g["date"].max())}


def _peers_in_band(df: pd.DataFrame, item: str, location: str,
                   start: str, end: str) -> list[str]:
    """Named peer locations that stayed in-band over the same window.

    This is the part that answers "maybe it was just a bad harvest".
    """
    w = df[(df["item"] == item) & (df["date"] >= start) & (df["date"] <= end)
           & (df["location"] != location)]
    if w.empty:
        return []
    # A peer counts as in-band if its typical price sits inside the expected
    # range. Median residual, not share-in-band: the share is hostage to the
    # band's own coverage rate, the median is not.
    med = w.groupby("location")["residual"].median().abs()
    return sorted(med[med <= PEER_IN_BAND_RESIDUAL].index.tolist())


def _expected_block(g: pd.DataFrame) -> dict:
    return {
        "rate": round(float(g["expected_mid"].median()), 2),
        "band": [round(float(g["expected_lo"].median()), 2),
                 round(float(g["expected_hi"].median()), 2)],
        "unit": str(g["unit"].iloc[0]),
    }


def _observed_block(g: pd.DataFrame) -> dict:
    mix = _tier_mix(g)
    return {"median": round(float(g["price"].median()), 2),
            "n": int(sum(mix.values())), "tier_mix": mix}


# --- 1. variance collapse ---------------------------------------------------

def variance_collapse(df: pd.DataFrame, refs: pd.DataFrame | None = None,
                      ids: "itertools.count" = None) -> list[dict]:
    """Independent sellers disagree. Sustained near-zero dispersion is the
    signature of a price that is being set once and repeated."""
    ids = ids or _counter()
    t = THRESHOLDS["variance_collapse"]
    out = []
    work = df.copy()
    work["comparable"] = comparable_price(work)

    for (item, location), g in work.groupby(["item", "location"], observed=True):
        daily = g.groupby("date").agg(
            cv=("comparable", lambda v: float(np.std(v) / np.mean(v)) if len(v) > 1
                and np.mean(v) else np.nan),
            sellers=("unit_id", "nunique"),
            out_of_band=("in_band", lambda v: 1.0 - float(np.mean(v))))
        daily = daily[daily["sellers"] >= t["min_sellers"]].dropna()
        if len(daily) < t["min_days"]:
            continue

        # Sellers agreeing on the competitive price is a working market, not a
        # finding. Dispersion only matters where it has collapsed *away* from the
        # reference rate — so both conditions must hold on the same days.
        hot = ((daily["cv"] <= t["cv_max"])
               & (daily["out_of_band"] >= t["min_out_of_band_share"]))
        if not hot.any():
            continue
        run_id = (~hot).cumsum()
        runs = hot.groupby(run_id).sum()
        if runs.max() < t["min_days"]:
            continue
        dates = hot.index[(run_id == runs.idxmax()) & hot]
        start, end = str(dates.min()), str(dates.max())
        win = g[(g["date"] >= start) & (g["date"] <= end)]
        if win.empty:
            continue
        cv = float(daily.loc[dates, "cv"].median())
        out.append(_emit(
            ids, tier=3, item=item, location=location,
            window={"start": start, "end": end}, detector="variance_collapse",
            statistic={"name": "median_daily_cv_across_sellers",
                       "value": round(cv, 4), "threshold": t["cv_max"],
                       "days_collapsed": int(runs.max())},
            expected=_expected_block(win), observed=_observed_block(win),
            residual_sd=round(float(win["residual"].std(ddof=0) or 0.0), 3),
            peers_in_band=_peers_in_band(df, item, location, start, end),
        ))
    return out


# --- 2. cost correlation (the headline metric) ------------------------------

def _rolling_corr(a: pd.Series, b: pd.Series, window: int) -> float:
    joined = pd.concat([a, b], axis=1).dropna()
    if len(joined) < window:
        return float("nan")
    r = joined.iloc[:, 0].rolling(window).corr(joined.iloc[:, 1])
    return float(r.median()) if r.notna().any() else float("nan")


def cost_correlation(df: pd.DataFrame, refs: pd.DataFrame | None = None,
                     ids: "itertools.count" = None) -> list[dict]:
    """Competitive prices track costs. Collusive prices track each other.

    For each seller: rolling correlation against the peer median, and against the
    cost driver. A price that follows its neighbours far more closely than it
    follows its own costs is the thing this whole project is about.
    """
    ids = ids or _counter()
    t = THRESHOLDS["cost_correlation"]
    out = []

    for (item, location), g in df.groupby(["item", "location"], observed=True):
        daily = (g.groupby(["date", "unit_id"], observed=True)
                 .agg(price=("price", "median"), cost=("cost_driver", "median"))
                 .reset_index())
        wide = daily.pivot(index="date", columns="unit_id", values="price").sort_index()
        cost = daily.groupby("date")["cost"].median().sort_index()
        # A correlation needs a series. Most report localities appear once or
        # twice and carry no time series; correlating them produces only NaN.
        dense = [c for c in wide.columns
                 if wide[c].notna().sum() >= t["min_days"]]
        wide = wide[dense]
        if wide.shape[1] < MIN_SELLERS_FOR_TIER_3 or len(wide) < t["min_days"]:
            continue

        # rolling correlation series per seller, then the median across sellers,
        # so the flag can name *when* prices decoupled rather than reporting the
        # whole history as one undifferentiated window
        peer_series, cost_series = [], []
        for seller in wide.columns:
            own = wide[seller]
            peers = wide.drop(columns=[seller]).median(axis=1)
            peer_series.append(own.rolling(t["window"], min_periods=t["window"]).corr(peers))
            cost_series.append(own.rolling(t["window"], min_periods=t["window"]).corr(cost))
        peer_roll = pd.concat(peer_series, axis=1).median(axis=1)
        cost_roll = pd.concat(cost_series, axis=1).median(axis=1)

        hot = ((peer_roll >= t["peer_min"]) & (cost_roll <= t["cost_max"])
               & ((peer_roll - cost_roll) >= t["gap_min"])).fillna(False)
        if not hot.any():
            continue
        run_id = (~hot).cumsum()
        runs = hot.groupby(run_id).sum()
        if runs.max() < t["min_days"]:
            continue
        dates = hot.index[(run_id == runs.idxmax()) & hot]
        first = wide.index.get_loc(dates.min())
        start = str(wide.index[max(0, first - t["window"] + 1)])
        end = str(dates.max())

        peer_c = float(peer_roll[dates].median())
        cost_c = float(cost_roll[dates].median())
        gap = peer_c - cost_c
        g = g[(g["date"] >= start) & (g["date"] <= end)]
        if g.empty:
            continue
        out.append(_emit(
            ids, tier=3, item=item, location=location,
            window={"start": start, "end": end}, detector="cost_correlation",
            statistic={"name": "peer_corr_minus_cost_corr", "value": round(gap, 3),
                       "threshold": t["gap_min"],
                       "peer_correlation": round(peer_c, 3),
                       "cost_correlation": round(cost_c, 3)},
            expected=_expected_block(g), observed=_observed_block(g),
            residual_sd=round(float(g["residual"].std(ddof=0) or 0.0), 3),
            peers_in_band=_peers_in_band(df, item, location, start, end),
        ))
    return out


# --- 3. persistence ---------------------------------------------------------

def persistence(df: pd.DataFrame, refs: pd.DataFrame | None = None,
                ids: "itertools.count" = None) -> list[dict]:
    """A price above the band for one day is weather. Above it for weeks while
    named neighbours stay inside is not."""
    ids = ids or _counter()
    t = THRESHOLDS["persistence"]
    out = []

    for (item, location), g in df.groupby(["item", "location"], observed=True):
        daily = g.groupby("date")["residual"].median().sort_index()
        above = daily >= t["residual_min"]
        if not above.any():
            continue
        # longest consecutive run above the threshold
        run_id = (~above).cumsum()
        runs = above.groupby(run_id).agg(["sum", "size"])
        best = runs["sum"].max()
        if best < t["min_consecutive_days"]:
            continue
        key = runs["sum"].idxmax()
        dates = daily.index[(run_id == key) & above]
        start, end = str(dates.min()), str(dates.max())

        win = g[(g["date"] >= start) & (g["date"] <= end)]
        peers = _peers_in_band(df, item, location, start, end)
        if not peers:
            # without an in-band peer we cannot rule out a district-wide shock
            continue
        out.append(_emit(
            ids, tier=2, item=item, location=location,
            window={"start": start, "end": end}, detector="persistence",
            statistic={"name": "consecutive_days_above_band", "value": int(best),
                       "threshold": t["min_consecutive_days"]},
            expected=_expected_block(win), observed=_observed_block(win),
            residual_sd=round(float(win["residual"].std(ddof=0) or 0.0), 3),
            peers_in_band=peers,
        ))
    return out


# --- 4. quantisation --------------------------------------------------------

def quantisation(df: pd.DataFrame, refs: pd.DataFrame | None = None,
                 ids: "itertools.count" = None) -> list[dict]:
    """Metered prices vary with distance. Negotiated-away prices land on round
    numbers and stop responding to how far you are going."""
    ids = ids or _counter()
    t = THRESHOLDS["quantisation"]
    out = []

    for (item, location), g in df.groupby(["item", "location"], observed=True):
        g = g[g["distance_km"].notna() & g["price"].notna()]
        if len(g) < t["min_obs"]:
            continue

        # Locate the period the clustering actually holds over. Averaged across
        # a whole history, a fare pattern that started in June is diluted by the
        # months before it and never crosses the threshold.
        is_round = np.isclose(g["price"] % t["round_to"], 0)
        daily = (pd.DataFrame({"date": g["date"].to_numpy(), "round": is_round})
                 .groupby("date")["round"].mean().sort_index())
        rolled = daily.rolling(t["roll_days"], min_periods=t["roll_days"]).mean()
        hot = rolled >= t["round_mass_min"]
        if not hot.any():
            continue
        run_id = (~hot).cumsum()
        runs = hot.groupby(run_id).sum()
        if runs.max() < t["min_days"]:
            continue
        dates = hot.index[(run_id == runs.idxmax()) & hot]
        # the rolling mean is right-aligned, so the run began roll_days earlier
        first = daily.index.get_loc(dates.min())
        start = str(daily.index[max(0, first - t["roll_days"] + 1)])
        end = str(dates.max())
        g = g[(g["date"] >= start) & (g["date"] <= end)]
        if len(g) < t["min_obs"]:
            continue
        mass = float(np.mean(np.isclose(g["price"] % t["round_to"], 0)))

        x = g["distance_km"].to_numpy(float)
        y = g["price"].to_numpy(float)
        if x.std() == 0:
            continue
        slope, intercept = np.polyfit(x, y, 1)
        pred = slope * x + intercept
        ss_res = float(((y - pred) ** 2).sum())
        ss_tot = float(((y - y.mean()) ** 2).sum())
        r2 = 1 - ss_res / ss_tot if ss_tot else 0.0

        if not (mass >= t["round_mass_min"] and r2 <= t["r2_max"]):
            continue

        out.append(_emit(
            ids, tier=3, item=item, location=location,
            window={"start": start, "end": end}, detector="quantisation",
            statistic={"name": "modal_mass_at_round_values", "value": round(mass, 3),
                       "threshold": t["round_mass_min"],
                       "distance_r2": round(float(r2), 3),
                       "distance_r2_threshold": t["r2_max"]},
            expected=_expected_block(g), observed=_observed_block(g),
            residual_sd=round(float(g["residual"].std(ddof=0) or 0.0), 3),
            peers_in_band=_peers_in_band(df, item, location, start, end),
        ))
    return out


DETECTORS = [variance_collapse, cost_correlation, persistence, quantisation]


def run_all(df: pd.DataFrame, refs: pd.DataFrame | None = None) -> list[dict]:
    ids = _counter()
    flags: list[dict] = []
    for fn in DETECTORS:
        found = fn(df, refs, ids)
        print(f"    {fn.__name__:20s} {len(found)} flag(s)")
        flags.extend(found)
    return flags
