# Basemap source

`overpass_raw.json.gz` — one Overpass query, run once by hand, for the roads,
railways and water inside the fixed heatmap frame (12.885–12.985 N,
79.070–79.345 E). 6.6 MB uncompressed, 0.95 MB committed.

Regenerate only if the frame in `pipeline/heatmap.py` changes:

```
curl -X POST -d @query.ql https://overpass-api.de/api/interpreter \
  | gzip -9 > overpass_raw.json.gz
```

```
[out:json][timeout:180];
(
  way["highway"~"^(motorway|trunk|primary|secondary|tertiary|unclassified|residential|motorway_link|trunk_link|primary_link|secondary_link)$"](12.885,79.070,12.985,79.345);
  way["railway"~"^(rail|light_rail)$"](12.885,79.070,12.985,79.345);
  way["waterway"~"^(river|stream|canal)$"](12.885,79.070,12.985,79.345);
  way["natural"="water"](12.885,79.070,12.985,79.345);
  way["landuse"="reservoir"](12.885,79.070,12.985,79.345);
);
out geom;
```

Then `python -m tools.make_basemap`.

**This is the only file in the project that came off the network at authoring
time, and nothing reads it over the network.** `tools.make_basemap` reads the
gzip from disk and writes `web/public/data/basemap.json`; `pipeline.build` and
the demo never touch either. Verify with the wifi off.

© OpenStreetMap contributors, ODbL. The attribution is carried in
`basemap.json` and rendered in the map corner. Do not remove it — the licence
requires it.
