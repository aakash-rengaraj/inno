"""Where things are on disk, anchored to the repository rather than to `cwd`.

Every path in this project used to be relative — `Path("data/raw")`,
`Path("web/dist-console")` — which silently required the process to have been
started from the repository root. That held for `python -m pipeline.build` run by
hand and broke the moment the app ran as a Windows service, where the working
directory is whatever the service manager chose. The failure is not a clean
"file not found" either: the server starts, then dies during startup inside the
ingest, several frames from the actual cause.

Anchoring on __file__ makes every entry point work from anywhere.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
OBSERVATIONS = PROCESSED / "observations.parquet"

SCHEMA = ROOT / "schema"
WEB = ROOT / "web"
WEB_DATA = WEB / "public" / "data"
DIST_PUBLIC = WEB / "dist-public"
DIST_CONSOLE = WEB / "dist-console"

SERVER_DATA = ROOT / "server" / "data"
