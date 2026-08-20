"""Overpass extract -> a compact basemap for the fixed heatmap frame.

    python -m tools.make_basemap

Reads the committed `data/raw/basemap/overpass_raw.json` and writes
`web/public/data/basemap.json`. Network is used **once**, by hand, to produce the
raw file; this converter and everything downstream of it read only from disk, so
`pipeline.build` and the demo stay offline. That is the same arrangement as every
other source in data/raw.

OpenStreetMap contributors, ODbL. The attribution is carried in the output and
rendered in the map corner -- the licence requires it and it must not be dropped.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

from pipeline.heatmap import FRAME
from pipeline import paths

# The heatmap viewBox. The frame never pans or zooms, so the projection is known
# at build time and the basemap ships as six merged path strings rather than
# 9,663 <path> elements -- React reconciling ten thousand nodes on every hover
# is the difference between a map and a slideshow. Must match W/H in Heatmap.jsx.
VIEW_W, VIEW_H = 1000.0, 372.0

# 6.6 MB of Overpass JSON, committed gzipped -- same as the Agmarknet exports.
RAW = paths.RAW / "basemap" / "overpass_raw.json.gz"
OUT = paths.WEB_DATA / "basemap.json"

ATTRIBUTION = "(c) OpenStreetMap contributors, ODbL"

# Roads are drawn in three weights, not fourteen. At 30 m per pixel a residential
# street and an unclassified lane are the same one-pixel line, and giving them
# separate styles only spends bytes.
CLASSES = {
    "motorway": "major", "trunk": "major", "primary": "major",
    "motorway_link": "major", "trunk_link": "major", "primary_link": "major",
    "secondary": "minor", "secondary_link": "minor", "tertiary": "minor",
    "unclassified": "street", "residential": "street",
}

# Simplification tolerance. The frame is ~29.8 km across a 1000-unit viewBox, so
# one unit is ~30 m; 12 m is well under half a pixel and invisible at the only
# scale this map is ever drawn at.
TOLERANCE_M = 12.0
M_PER_DEG_LAT = 110_574.0
M_PER_DEG_LNG = 108_400.0


def _perp(p, a, b) -> float:
    """Point-to-segment distance in metres, flat-earth (fine over 30 km)."""
    px, py = (p[1] - a[1]) * M_PER_DEG_LNG, (p[0] - a[0]) * M_PER_DEG_LAT
    bx, by = (b[1] - a[1]) * M_PER_DEG_LNG, (b[0] - a[0]) * M_PER_DEG_LAT
    seg = bx * bx + by * by
    if seg == 0:
        return (px * px + py * py) ** 0.5
    t = max(0.0, min(1.0, (px * bx + py * by) / seg))
    dx, dy = px - t * bx, py - t * by
    return (dx * dx + dy * dy) ** 0.5


def simplify(pts: list, tol: float = TOLERANCE_M) -> list:
    """Douglas-Peucker, iterative: some ways here have 2,000+ nodes."""
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        far, dmax = -1, tol
        for k in range(i + 1, j):
            d = _perp(pts[k], pts[i], pts[j])
            if d > dmax:
                far, dmax = k, d
        if far > 0:
            keep[far] = True
            stack.append((i, far))
            stack.append((far, j))
    return [p for p, k in zip(pts, keep) if k]


def _clip_flag(pts: list) -> bool:
    """Keep a way if any node is inside the frame; the renderer clips the rest."""
    return any(FRAME["lat_min"] <= a <= FRAME["lat_max"]
               and FRAME["lng_min"] <= b <= FRAME["lng_max"] for a, b in pts)


def _to_path(ways: list) -> str:
    """One `d` string per layer. Coordinates are rounded to 0.1 viewBox units --
    a thirtieth of a pixel at the scale this is drawn, and it halves the file."""
    lng_span = FRAME["lng_max"] - FRAME["lng_min"]
    lat_span = FRAME["lat_max"] - FRAME["lat_min"]
    out = []
    for pts in ways:
        seg = []
        last = None
        for lat, lng in pts:
            x = round((lng - FRAME["lng_min"]) / lng_span * VIEW_W, 1)
            y = round((1 - (lat - FRAME["lat_min"]) / lat_span) * VIEW_H, 1)
            if (x, y) == last:          # rounding can collapse adjacent nodes
                continue
            seg.append(f"{x:g} {y:g}")
            last = (x, y)
        if len(seg) > 1:
            out.append("M" + "L".join(seg))
    return "".join(out)


def main() -> None:
    with gzip.open(RAW, "rt") as fh:
        raw = json.load(fh)
    layers: dict[str, list] = {"major": [], "minor": [], "street": [],
                               "rail": [], "water": [], "waterbody": []}
    nodes_in = nodes_out = 0

    for el in raw.get("elements", []):
        geom = el.get("geometry") or []
        if len(geom) < 2:
            continue
        tags = el.get("tags", {})
        if tags.get("highway"):
            layer = CLASSES.get(tags["highway"])
        elif tags.get("railway"):
            layer = "rail"
        elif tags.get("waterway"):
            layer = "water"
        elif tags.get("natural") == "water" or tags.get("landuse") == "reservoir":
            layer = "waterbody"
        else:
            layer = None
        if layer is None:
            continue

        pts = [(g["lat"], g["lon"]) for g in geom]
        if not _clip_flag(pts):
            continue
        nodes_in += len(pts)
        pts = simplify(pts)
        nodes_out += len(pts)
        layers[layer].append(pts)

    payload = {
        "frame": dict(FRAME),
        "view": [VIEW_W, VIEW_H],
        "attribution": ATTRIBUTION,
        "source": "OpenStreetMap via overpass-api.de",
        "paths": {name: _to_path(ways) for name, ways in layers.items()},
        "ways": {name: len(ways) for name, ways in layers.items()},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, separators=(",", ":")) + "\n")

    kb = OUT.stat().st_size / 1024
    print(f"  {RAW.stat().st_size / 1e6:.1f} MB gzipped raw -> {kb:.0f} kB")
    print(f"  {nodes_in:,} nodes -> {nodes_out:,} after simplification "
          f"({TOLERANCE_M:.0f} m tolerance)")
    for name, ways in layers.items():
        print(f"    {name:10s} {len(ways):5d} ways  "
              f"{len(payload['paths'][name]) / 1024:6.0f} kB")


if __name__ == "__main__":
    main()
