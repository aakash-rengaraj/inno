"""Locality generalisation.

Field reports are pseudonymised to a ~50m grid cell, which means the coordinate
*is* the identity. That has a failure mode: a single reporter standing 100m away
the next day becomes a second "independent seller", and three such reports clear
the evidence floor on their own. The floor is supposed to be an anti-gaming
defence, and at grid resolution it is trivially defeated.

This step merges reporting points that are both close together and quoting the
same price into one locality, and independence is then counted in localities.
Two people 40m apart quoting the same rupee figure are one observation of one
locality, not corroboration.

Applied to tier C only. For a commercial listing the seller identity is the
platform, not the coordinate — three platforms serving the same pincode share a
centroid but are genuinely independent, and merging them would silently destroy
the dispersion and correlation detectors.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

GENERALISER = {
    "radius_m": 150.0,        # merge reporting points closer than this ...
    "price_tolerance": 0.03,  # ... whose typical price agrees within 3%
}

EARTH_R = 6_371_000.0


def _haversine_matrix(lat: np.ndarray, lng: np.ndarray) -> np.ndarray:
    """Pairwise great-circle distance in metres."""
    la = np.radians(lat)[:, None]
    lo = np.radians(lng)[:, None]
    dlat = la - la.T
    dlng = lo - lo.T
    a = np.sin(dlat / 2) ** 2 + np.cos(la) * np.cos(la.T) * np.sin(dlng / 2) ** 2
    return 2 * EARTH_R * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


class _Union:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))

    def find(self, i: int) -> int:
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def union(self, i: int, j: int) -> None:
        ri, rj = self.find(i), self.find(j)
        if ri != rj:
            self.parent[max(ri, rj)] = min(ri, rj)


def _cluster(points: pd.DataFrame, radius_m: float, tol: float) -> dict[str, int]:
    """Single-linkage merge on (proximity AND price agreement)."""
    n = len(points)
    if n == 1:
        return {points["seller_id"].iloc[0]: 0}

    lat = points["lat"].to_numpy(float)
    lng = points["lng"].to_numpy(float)
    price = points["price"].to_numpy(float)

    near = _haversine_matrix(lat, lng) <= radius_m
    # relative price gap between every pair
    denom = (price[:, None] + price[None, :]) / 2
    denom[denom == 0] = np.nan
    same_price = np.abs(price[:, None] - price[None, :]) / denom <= tol

    mergeable = near & same_price
    uf = _Union(n)
    for i, j in zip(*np.where(np.triu(mergeable, k=1))):
        uf.union(int(i), int(j))

    roots = [uf.find(i) for i in range(n)]
    order = {r: k for k, r in enumerate(sorted(set(roots)))}
    return {sid: order[r] for sid, r in zip(points["seller_id"], roots)}


def assign_localities(df: pd.DataFrame, radius_m: float | None = None,
                      price_tolerance: float | None = None) -> pd.Series:
    """Return a locality id per row. Independence is counted on this, not on
    seller_id.

    Tiers A and B keep their own seller identity: a mandi is a mandi and a
    platform is a platform, whatever their coordinates say.
    """
    radius_m = GENERALISER["radius_m"] if radius_m is None else radius_m
    tol = GENERALISER["price_tolerance"] if price_tolerance is None else price_tolerance

    locality = df["seller_id"].astype(str).copy()
    reports = df["tier"] == "C"
    if not reports.any():
        return locality

    sub = df[reports]
    for (item, location), g in sub.groupby(["item", "location"], observed=True):
        points = (g.groupby("seller_id", observed=True)
                  .agg(lat=("lat", "mean"), lng=("lng", "mean"),
                       price=("price", "median"))
                  .reset_index())
        mapping = _cluster(points, radius_m, tol)
        ids = g["seller_id"].map(lambda s: f"{location}_loc{mapping[s]:03d}")
        locality.loc[g.index] = ids
    return locality


def summarise(df: pd.DataFrame, locality: pd.Series) -> dict:
    """What the generaliser actually collapsed — reported on the case file so the
    officer can see that corroboration was counted conservatively."""
    reports = df["tier"] == "C"
    before = int(df.loc[reports, "seller_id"].nunique())
    after = int(locality[reports].nunique())
    return {
        "radius_m": GENERALISER["radius_m"],
        "price_tolerance": GENERALISER["price_tolerance"],
        "report_points": before,
        "report_localities": after,
        "collapsed": before - after,
    }
