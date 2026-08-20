"""HTTP API for the review system.

Deliberate departure from CLAUDE.md sections 0 and 8, which rule out any server.
Requested explicitly: without one, a citizen report can only reach the console by
a manual CSV drop and rebuild. The static build in web/public/data remains valid
and is still what `python -m pipeline.build` produces, so the demo has a path
that works with the server dead.

    uvicorn server.app:app --reload --port 8000
"""
from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from pipeline.contracts import json_safe
from pipeline.ingest import reports as reports_ingest
from server import db
from server.engine import ENGINE

CONSOLE_TOKEN = os.environ.get("CONSOLE_TOKEN", "vellore-dso-2026")

# When the frontends are served from this app there is no cross-origin request to
# allow. ALLOWED_ORIGINS only matters when the pages are hosted elsewhere (e.g.
# vite on :5173 during development).
ALLOWED_ORIGINS = [o.strip() for o in
                   os.environ.get("ALLOWED_ORIGINS", "*").split(",") if o.strip()]

# A public POST endpoint on a real domain will be found. The evidence floor and
# locality generalisation stop junk becoming a flag; this stops it filling the disk.
REPORTS_PER_HOUR = int(os.environ.get("REPORTS_PER_HOUR", "30"))
_hits: dict[str, deque] = defaultdict(deque)

ITEM_UNITS = {"tomato": "per_kg", "onion": "per_kg",
              "egg_table": "per_piece", "auto_ride": "per_ride"}

app = FastAPI(title="Price Review API", version="1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_methods=["*"],
    allow_headers=["*"], allow_credentials=False,
)


@app.middleware("http")
async def rate_limit_reports(request: Request, call_next):
    if request.method == "POST" and request.url.path == "/api/reports":
        who = request.client.host if request.client else "unknown"
        window, now_s = 3600.0, time.monotonic()
        seen = _hits[who]
        while seen and now_s - seen[0] > window:
            seen.popleft()
        if len(seen) >= REPORTS_PER_HOUR:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many reports from this connection. "
                                   "Try again later."})
        seen.append(now_s)
    return await call_next(request)

CONN = db.connect()


@app.on_event("startup")
def _startup() -> None:
    db.init(CONN)
    print("starting engine (parsing data/raw, fitting band model)")
    ENGINE.start()
    print(f"console token: {CONSOLE_TOKEN}")


# --- auth ------------------------------------------------------------------

def console_auth(x_console_token: str = Header(default="")) -> str:
    """Shared passphrase. Not user accounts — it separates the citizen surface
    from the enforcement surface, which now names flagged locations over HTTP."""
    if x_console_token != CONSOLE_TOKEN:
        raise HTTPException(status_code=401, detail="Console token required.")
    return x_console_token


# --- models ----------------------------------------------------------------

class ReportIn(BaseModel):
    item: Literal["tomato", "onion", "egg_table", "auto_ride"]
    price_inr: float = Field(gt=0, le=100000)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    distance_km: float | None = Field(default=None, gt=0, le=200)
    note: str = ""
    submitted_at: str | None = None


class ActionIn(BaseModel):
    flag_id: str
    from_: str = Field(alias="from")
    to: Literal["queued", "assigned", "inspected", "closed"]
    officer: str
    note: str = ""

    model_config = {"populate_by_name": True}


# --- public ----------------------------------------------------------------

@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "flags_in_queue": len(ENGINE.artifacts.get("queue", [])),
            "last_recompute": ENGINE.last_recompute}


@app.get("/api/public/meta")
def public_meta() -> dict:
    return json_safe(ENGINE.public_meta())


@app.post("/api/reports", status_code=201)
def submit_report(body: ReportIn) -> dict:
    if body.item == "auto_ride" and not body.distance_km:
        raise HTTPException(422, "A fare report needs the trip distance.")

    row = {
        "submitted_at": body.submitted_at or db.now(),
        "lat": body.lat, "lng": body.lng, "item": body.item,
        "price_inr": round(body.price_inr, 2), "unit": ITEM_UNITS[body.item],
        "distance_km": body.distance_km,
        "note": body.note.replace(",", " ").replace("\n", " ")[:60],
    }

    # Run it through the real ingest before storing: a row that the pipeline
    # would reject should be rejected at the door, with the same reason.
    import pandas as pd
    try:
        normalised = reports_ingest.normalise(pd.DataFrame([{**row}]))
    except AssertionError as exc:
        raise HTTPException(422, f"Report rejected: {exc}") from exc
    if normalised.empty:
        raise HTTPException(422, "Report rejected: missing geotag or timestamp.")

    report_id = db.insert_report(CONN, row)
    # A report counts as evidence on arrival, so detection re-runs now. What
    # stops one reporter manufacturing a flag is not review but the evidence
    # floor plus locality generalisation: nearby reports quoting the same price
    # collapse to a single locality and corroborate nothing.
    stats = ENGINE.recompute(db.all_reports(CONN))
    return {
        "id": report_id,
        "location": str(normalised["location"].iloc[0]),
        "seller_id": str(normalised["seller_id"].iloc[0]),
        "recompute": stats,
        "message": ("Recorded as a tier C observation. Your coordinates are stored "
                    "as a ~50m grid cell, never an address."),
    }


# --- console ---------------------------------------------------------------

@app.get("/api/queue", dependencies=[Depends(console_auth)])
def queue() -> list:
    return json_safe(ENGINE.artifacts.get("queue", []))


@app.get("/api/flags", dependencies=[Depends(console_auth)])
def flags() -> list:
    return json_safe(ENGINE.artifacts.get("flags", []))


@app.get("/api/cases", dependencies=[Depends(console_auth)])
def cases() -> dict:
    return json_safe(ENGINE.artifacts.get("cases", {}))


@app.get("/api/charts", dependencies=[Depends(console_auth)])
def charts() -> dict:
    return json_safe(ENGINE.artifacts.get("charts", {}))


@app.get("/api/meta", dependencies=[Depends(console_auth)])
def meta() -> dict:
    m = dict(ENGINE.artifacts.get("meta", {}))
    m["reports_received"] = db.report_count(CONN)
    m["last_recompute"] = ENGINE.last_recompute
    return json_safe(m)


@app.get("/api/actions", dependencies=[Depends(console_auth)])
def actions() -> list:
    return json_safe(db.list_actions(CONN))


@app.post("/api/actions", status_code=201, dependencies=[Depends(console_auth)])
def add_action(body: ActionIn) -> dict:
    known = {f["flag_id"] for f in ENGINE.artifacts.get("queue", [])}
    if body.flag_id not in known:
        raise HTTPException(404, f"{body.flag_id} is not in the inspection queue.")
    return json_safe(db.insert_action(CONN, {
        "flag_id": body.flag_id, "from": body.from_, "to": body.to,
        "officer": body.officer, "note": body.note}))


@app.post("/api/recompute", dependencies=[Depends(console_auth)])
def recompute() -> dict:
    return json_safe(ENGINE.recompute(db.all_reports(CONN)))


# --- serving the two frontends --------------------------------------------
#
# Mounted last so /api/* always wins. Serving both surfaces from this app means
# one domain, no CORS, and no second host to configure on demo day. They remain
# separate builds: the public bundle still has no flag data in it.

PUBLIC_DIR = Path("web/dist-public")
CONSOLE_DIR = Path("web/dist-console")

if CONSOLE_DIR.is_dir():
    app.mount("/console", StaticFiles(directory=CONSOLE_DIR, html=True), name="console")
if PUBLIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=PUBLIC_DIR, html=True), name="public")
