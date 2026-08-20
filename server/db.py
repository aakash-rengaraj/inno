"""SQLite storage for the two things that are not committed artifacts:
citizen reports and regulator actions.

Everything else — observations, flags, cases — is derived, and is recomputed
from data/raw plus the reports in here.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("server/data/review.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    submitted_at TEXT    NOT NULL,
    lat          REAL    NOT NULL,
    lng          REAL    NOT NULL,
    item         TEXT    NOT NULL,
    price_inr    REAL    NOT NULL,
    unit         TEXT    NOT NULL,
    distance_km  REAL,
    note         TEXT    DEFAULT ''
);

CREATE TABLE IF NOT EXISTS actions (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    flag_id  TEXT NOT NULL,
    from_st  TEXT NOT NULL,
    to_st    TEXT NOT NULL,
    officer  TEXT NOT NULL,
    note     TEXT DEFAULT '',
    at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_actions_flag ON actions(flag_id);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


# --- reports ---------------------------------------------------------------

def insert_report(conn: sqlite3.Connection, row: dict) -> int:
    cur = conn.execute(
        """INSERT INTO reports
           (submitted_at, lat, lng, item, price_inr, unit, distance_km, note)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (row["submitted_at"], row["lat"], row["lng"], row["item"], row["price_inr"],
         row["unit"], row.get("distance_km"), row.get("note", "")))
    conn.commit()
    return int(cur.lastrowid)


def reference(report_id: int) -> str:
    """Public reference a reporter can quote back. Derived from the row id, so
    it is stable and needs no extra column."""
    return f"RPT-{report_id:04d}"


def all_reports(conn: sqlite3.Connection) -> list[dict]:
    return [_report(dict(r)) for r in conn.execute("SELECT * FROM reports")]


def list_reports(conn: sqlite3.Connection, limit: int = 500) -> list[dict]:
    return [_report(dict(r)) for r in conn.execute(
        "SELECT * FROM reports ORDER BY id DESC LIMIT ?", (limit,))]


def _report(r: dict) -> dict:
    r["reference"] = reference(r["id"])
    return r


def report_count(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) n FROM reports").fetchone()["n"])


# --- actions ---------------------------------------------------------------

def insert_action(conn: sqlite3.Connection, a: dict) -> dict:
    cur = conn.execute(
        "INSERT INTO actions (flag_id, from_st, to_st, officer, note, at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (a["flag_id"], a["from"], a["to"], a["officer"], a.get("note", ""), now()))
    conn.commit()
    row = conn.execute("SELECT * FROM actions WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _action(dict(row))


def list_actions(conn: sqlite3.Connection, limit: int = 200) -> list[dict]:
    return [_action(dict(r)) for r in conn.execute(
        "SELECT * FROM actions ORDER BY id DESC LIMIT ?", (limit,))]


def _action(r: dict) -> dict:
    return {"id": f"ACT-{r['id']:04d}", "flag_id": r["flag_id"], "from": r["from_st"],
            "to": r["to_st"], "officer": r["officer"], "note": r["note"], "at": r["at"]}
