# Price Manipulation Detection — AIML-08

Detects anomalous and potentially collusive pricing by comparing observed prices
against published reference rates, and emits **case files**: printable evidence
documents aimed at a district supply officer or RTO enforcement desk.

> Competitive prices track costs. Collusive prices track each other.

The system produces **screens that prioritise investigation**. Nothing it emits
states that a party has manipulated prices.

## Run it

```bash
python -m pipeline.build     # regenerates every JSON artifact from data/raw
npm --prefix web run dev     # http://localhost:5173
```

`pipeline.build` reads only `data/raw` and never opens a socket. The frontend
reads static JSON from `web/public/data`. There is no API server.

Setup:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
brew install libomp          # macOS only — LightGBM links against OpenMP
```

## API server

A departure from SPEC.md sections 0 and 8, which rule out any HTTP server —
requested explicitly, because without one a citizen report can only reach the
console via a manual CSV drop and rebuild. `python -m pipeline.build` still
produces the static artifacts, so **the demo retains a path that works with the
server dead**.

```bash
CONSOLE_TOKEN=vellore-dso-2026 .venv/bin/uvicorn server.app:app --port 8000
```

FastAPI + SQLite (`server/data/review.db`). It owns report intake, action-board
state, and serving flags/cases/charts.

**Public, unauthenticated**

| | |
|---|---|
| `POST /api/reports` | citizen submission; validated through the real ingest, stored, then detection re-runs |
| `GET /api/public/meta` | aggregate counts only — no thresholds, no flags |

**Console, requires `X-Console-Token`**

| | |
|---|---|
| `GET /api/queue` `/flags` `/cases` `/charts` `/heatmap` `/meta` | computed artifacts |
| `GET`/`POST /api/actions` | action board, persisted |
| `POST /api/recompute` | manual trigger |

### Hosting on a domain

Build both frontends and let the API server serve them. One origin means no CORS
to configure and no second host to arrange on the day.

```bash
python -m tools.build_web          # -> web/dist-public, web/dist-console
CONSOLE_TOKEN='<something-not-this>' \
ALLOWED_ORIGINS='https://your.domain' \
REPORTS_PER_HOUR=30 \
  .venv/bin/uvicorn server.app:app --host 0.0.0.0 --port 8000
```

| Path | |
|---|---|
| `/` | public page |
| `/console` | enforcement console, passphrase-gated |
| `/api/*` | API; mounted before the static routes so it always wins |

`ALLOWED_ORIGINS` only matters if the pages are served from somewhere other than
this app (vite on :5173 during development). Defaults to `*`.

**Before putting this on a public domain:**

- Change `CONSOLE_TOKEN`. The default in the code is a development value.
- Terminate TLS in front of it. The console passphrase travels in a header, so
  over plain HTTP it is readable in transit.
- `REPORTS_PER_HOUR` (default 30/IP) limits the open intake endpoint. The evidence
  floor and the generaliser stop junk becoming a flag; this stops it filling the disk.
- The passphrase is a shared secret, not user accounts. It separates the citizen
  surface from the enforcement surface; it is not an audit trail of who did what
  beyond the officer name recorded on each action.

### Deploying to a Windows VPS

`deploy/sync.ps1` plus `deploy/README.md`. A scheduled task polls `main` every
two minutes, rebuilds only what changed, and restarts the service; NSSM keeps
uvicorn running. No inbound port is needed for deployment and no webhook or
secret is shared with GitHub.

Not a self-hosted GitHub Actions runner: the repo is public, and GitHub advises
against pairing the two, because a workflow triggered by a pull request runs a
stranger's code on the box.

`server/data/` is gitignored, so citizen reports and the action board survive a
deploy. Idle is ~46 MB; a recompute peaks near 645 MB, so size the box at 2 GB.

### Static fallback

Both frontends probe `/api/health` on load. With no server they fall back to the
artifacts embedded at build time and show a **Static build** badge: the console
skips the passphrase gate and serves the last built queue read-only. A dead server degrades the demo; it does not blank the screen.

### Two design points

**The band model is fitted once at startup, not per report.** A citizen report
does not change the Agmarknet backbone the band is fitted on, so refitting would
burn seconds to arrive at the same model. Startup ~2.7s; each recompute ~0.5s.

**A report counts as evidence on arrival.** There is no moderation step. What
stops one person manufacturing a flag is not human review but the evidence floor
plus locality generalisation (below) plus the rate limit — nearby reports quoting
the same price collapse to a single locality and corroborate nothing.

## Locality generalisation

`pipeline/generalise.py`. Field reports pseudonymise to a ~50m grid cell, so the
coordinate is the identity — and one reporter standing 100m away the next day
became a second "independent seller". Three such reports cleared the evidence
floor on their own, which defeats the point of the floor.

Reporting points now merge into one **locality** when they are both within 150m
and quoting prices within 3%. Independence is counted in localities.

```
673 report points -> 237 localities (436 collapsed)
  egg_table   276 -> 31     identical prices at jittered points
  tomato      313 -> 90     retail prices vary between shops
  auto_ride   284 -> 146    fares vary with distance
```

Independence counts on the five live flags fell from 58/60/62/34/53 to
**10/9/25/6/9**. No flag gained or lost its place in the queue.

Applied to **tier C only**. For a commercial listing the seller identity is the
platform, not the coordinate: three platforms serving one pincode share a
centroid, and merging them would silently destroy the dispersion and correlation
detectors.

### The loop, verified end to end

The withheld Ranipet pattern had two reporters 40m apart quoting the same price.
Under generalisation they are **one** locality, so padding from that spot cannot
clear the floor. Reports from four genuinely separated points do:

```
submitted from 2 points >300m apart, within the flag window
recompute: 0.52s, 7 live reports, 14,314 observations
queue 5 -> 6 flags
FLG-0004 vellore_ranipet  tier 1 -> tier 2, localities 1 -> 4   ENTERS QUEUE
```

That is the distinction the evidence floor is supposed to draw, and at grid
resolution it could not.

Reset demo state: `rm -rf server/data/review.db*`

## Heatmap

`pipeline/heatmap.py` -> `heatmap.json` -> the console **Map** tab. 1,514 field
reports binned to 150 m cells over a fixed frame of Vellore district.

Two decisions, because the obvious version of this feature is wrong in both:

**Colour is price deviation, not report count.** A density map of citizen reports
maps where people have phones and civic energy, not where prices are manipulated
-- Thorapadi would be the darkest zone in the district on 427 reports alone. The
cell value is the median gap between what reporters paid and the middle of the
modelled band, so a zone with 400 reports at fair prices renders cold and a
six-report cell paying 30% over renders hot. Count only drives opacity.

**Cells below the evidence floor are not drawn.** `cases.apply_evidence_floor`
keeps a finding out of the queue until three independent localities corroborate
it; a cell rendered from one walk-past would put on screen exactly the claim the
floor exists to withhold. 40 cells are suppressed on the current build.

The cell is 150 m -- the same radius `generalise.py` merges reporting points at,
so one cell is approximately one locality and the map is drawn at the resolution
the evidence is actually counted at.

**The frame is fixed** (12.885-12.985 N, 79.070-79.345 E) and the map does not
pan, zoom or scroll. An enforcement map that can be dragged off its own
jurisdiction invites reading a neighbouring district's prices as this district's
problem, and the 20 km of empty ground between Vellore city and Ranipet is
exactly where a smoothed, scrollable surface would invent confidence it does not
have. Cells are discrete squares; nothing is interpolated between clusters.

Filtered to eggs, the map independently reproduces the queue: Katpadi and Ranipet
are the only hot zones, which are the two egg findings -- one in the queue, one
withheld below the floor.

### Basemap

Roads, railways and water come from OpenStreetMap, drawn under the cells so a
cell is a recognisable place and not a square on graph paper.

**Not Leaflet or MapLibre.** Both exist to solve pan, zoom and
tile-loading-on-demand; the frame is fixed, so all three would have to be turned
off, and what remains of a slippy-map library after that is a div with images in
it. The deciding argument is offline: both need a tile server, and a map that
goes grey when the venue wifi drops fails visibly, mid-sentence, on the screen
everyone is looking at.

Instead the OSM geometry is fetched **once, by hand** into
`data/raw/basemap/overpass_raw.json.gz` (0.95 MB gzipped) and committed, exactly
like the Agmarknet and NECC exports. `tools.make_basemap` reads it from disk:

```
1.0 MB gzipped raw -> 313 kB
65,331 nodes -> 28,415 after simplification (12 m tolerance)
  major   432   minor   192   street  8755   rail  148   water  77   waterbody  59
```

Because the frame never moves, the projection is known at build time, so the
9,663 ways ship as **six merged path strings** already in viewBox coordinates.
The whole map is 106 SVG nodes; React is not asked to reconcile ten thousand of
them on every hover. Simplification tolerance is 12 m against a scale of ~30 m
per viewBox unit — under half a pixel, invisible at the only size this is drawn.

Roads are three weights, in grey only. The map is context; the colour on it is
the finding. Attribution (ODbL) is rendered in the corner and must not be
removed.

**Console-only.** At 150 m a hot cell is close to naming a shop. It is served
from `/api/heatmap` behind the passphrase and stripped from the public build.

## Two separate surfaces

The public page and the enforcement console are **separate builds with separate
entry points**, not two tabs of one app. There is no navigation between them.

```bash
npm --prefix web run dev     # / = console, /report.html = public page
SURFACE=public  npx vite build --outDir dist-public
SURFACE=console npx vite build --outDir dist-console
```

The separation is enforced by what each bundle *contains*, not by hiding links.
Vite copies the whole of `web/public` into every dist, so the public build was
shipping `flags.json`, `cases.json`, `cases.xml`, `charts.json` and
`heatmap.json` as static files -- fetchable by path whatever the bundle chose to
render. `tools.build_web` now deletes them from `dist-public` and projects
`meta.json` down to the same `PUBLIC_META_FIELDS` whitelist the live
`/api/public/meta` uses, so the static fallback withholds what the served
surface withholds.
The public build embeds only aggregate counts from `meta.json` — it carries no
flag ids, no case narratives, no detector names, no thresholds and no model
internals, so it cannot name a flagged location even from page source. Note that
`meta.json` as written for the console includes the full `THRESHOLDS` dict;
publishing that to consumers would tell a manipulator exactly how to price just
under each trigger, so the public packaging step projects `meta` down to a
whitelist of aggregate fields.

Screens, public surface:

1. **Landing** — what the system compares, how a flag is made, and what it
   explicitly does not claim.
2. **Report a price** — a citizen submits what they were charged. Emits exactly
   the CSV row `pipeline/ingest/reports.py` parses, downloadable as
   `field_reports.csv`. Verified round-trip: the form's output parses cleanly,
   rejects rows lacking a geotag or timestamp, and pseudonymises to a ~50m grid.

Screens, enforcement console (internal):

3. **Queue** — flags sorted by priority then distance from the reference rate.
4. **Flag detail** — chart plus the evidence breakdown and the measure applied.
5. **Case file** — one button from the detail; print-styled A4.
6. **Action board** — what is under review and what has been done about it.
   Flags move `Awaiting review → Assigned → Inspection completed → Closed`, each
   transition logged with officer, outcome and timestamp.

### On "real time"

Section 8 rules out WebSockets and real-time updates, and there is no server, so
the action board is live via `localStorage` plus the browser's own `storage`
event: two tabs open on the same machine see each other's actions immediately,
with no reload and no polling. Verified by writing from one tab and watching the
counts, the status pill and the activity log move in the other. It is genuinely
live; it is not networked, and the UI says so on screen. "Clear log" resets it
before a rehearsal.

What the queue currently contains:

| Ref | Vertical | Location | Finding |
|---|---|---|---|
| FLG-0002 | Eggs | Katpadi | Prices track each other, not costs (peer corr 0.98 vs cost corr −0.21) |
| FLG-0001 | Eggs | Katpadi | Dispersion across sellers collapsed to 0.2% for 71 days |
| FLG-0006 | Autos | Katpadi | 93% of fares on round multiples, distance R² 0.21 |
| FLG-0005 | Commodities | Vaniyambadi | Sustained gap above the modelled band |
| FLG-0003 | Eggs | Katpadi | 50 consecutive days above the expected range |

One further pattern (Ranipet, eggs) is detected and **withheld**: it rests on
field reports from 2 independent locations, below the 3-seller evidence floor.
It is downgraded to tier 1 and excluded from the queue by an assertion in
`cases.apply_evidence_floor`, not by convention.

## Layout

```
data/raw          committed source files, never regenerated during the demo
data/processed    observations.parquet — the single shared table
pipeline/ingest   one module per source, all emitting the Observation schema
pipeline/contracts.py   the frozen schemas, enforced with assertions
pipeline/model.py       quantile band model
pipeline/expectations.py  what a price should have been, per vertical
pipeline/generalise.py  reporting points -> localities
pipeline/detect.py      the four detectors
pipeline/cases.py       flag -> narrative -> case file
pipeline/build.py       runs everything, writes web/public/data/*.json
web               Vite + React + Recharts
```

## Deviations from the handoff spec

Five, all deliberate. Each is commented at the site.

**1. Agmarknet no longer has the documented interface.** `agmarknet.gov.in` has
been rebuilt as a React SPA whose data API sits behind a `/captcha/` endpoint;
the `__VIEWSTATE` / `__EVENTVALIDATION` postback flow described in §5.1 does not
exist any more. Bot-detection was not bypassed. Live scraping is therefore an
open decision — see "Data" below.

**2. The band model is fitted in relative space** (`log(price / regional peer
level)`), not on price. Fitted on price directly, the model learns the direction
of the training period's trend and extrapolates it; our history is one long
upswing, so in a falling market every honest location lands below the band. In
relative space the trend cancels, and the modelled quantity is the one the
project is actually about.

**3. Lags are of supply, not of own price.** §5.2 lists lagged price at 1/7/30
days. Any feature carrying a location's *own* price history lets a manipulated
market justify itself: yesterday's collusive price predicts today's, the residual
collapses, and the detectors go quiet exactly where they should fire. This was
measured, not assumed — with own-price lags the suspect market never left the
band.

**4. The regional peer level is a leave-one-out median, not a mean.** With a
mean, one manipulated market lifts the expected band for its own honest peers and
pushes *them* out of it.

## Model validation

Time-based split (never random — a random split leaks future prices into
training). Held-out coverage at the nominal 80% band:

- onion, never manipulated: **0.756** — inside the 75–85% gate
- full backbone: 0.742
- all validation rows: 0.656

The gap is the manipulation contaminating its own peer level, which is a real
property of a peer-relative band and is visible in the tomato series specifically.

**Known limitation, worth saying on stage:** a band defined against peers cannot
see a conspiracy that moves every location in the region at once. Cost-correlation
(detector 2) partially covers that gap, since it compares each seller against the
published rate rather than against neighbours.

## Data

`data/raw` currently holds **synthetic** files generated by
`python -m tools.make_fixture`. They are written in the formats the real upstream
sources emit, so the ingest parsers do real parsing work and can be pointed at
genuine scrape output file-by-file with no code change. `data/raw/README.md`
repeats this warning at the point of use.

Every number in the demo is computed by the real pipeline from those files;
nothing in the frontend is hardcoded. What is synthetic is the input, not the
analysis.

## Privacy and language discipline

- `seller_id` is always pseudonymous — a SHA-1 prefix for commercial sources, a
  ~50m coordinate grid cell for field reports. No real business name enters the
  pipeline, and `contracts.validate_observations` rejects anything that isn't a
  lowercase snake-case id.
- Field reports without a geotag or timestamp are rejected at ingest (29 of 2,933
  in the current fixture).
- `validate_flag` refuses to construct a flag whose narrative contains "proven",
  "proves", "cartel", or "guilty".
- Narratives are rendered by a template in `cases.py`. Deterministic, no LLM —
  they are read aloud on stage and must not vary between builds.
