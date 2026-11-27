"""SQLite persistence (stdlib ``sqlite3``).

The live operating picture (trips, bookings, incidents in flight) is regenerated in memory, but the
records that must survive a restart live here:

* ``contacts``            travelers with real e-mail and mobile numbers; the seed reads them from this table
* ``delivery_log``        every e-mail / SMS attempt with its provider result
* ``incident_log``        audit trail of incident status changes
* ``crowd_observations``  one row per analysed camera frame
* ``crowd_reroutes``      reroute advisories sent from the crowd monitor
* ``flight_cache``        last AviationStack response per airport and direction
* ``api_usage``           calls made to metered APIs per day

Each call opens a short-lived connection (WAL mode), so it is safe from request threads and LangGraph workers.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from contextlib import closing
from pathlib import Path
from typing import Any, Iterable

from app.config import settings
from app.core.utils import iso, now
from app.data import reference as ref

log = logging.getLogger("arro.db")

_write_lock = threading.Lock()
_ready = False

SCHEMA = """
CREATE TABLE IF NOT EXISTS contacts (
    pnr         TEXT PRIMARY KEY,
    first_name  TEXT NOT NULL,
    last_name   TEXT NOT NULL,
    email       TEXT,
    phone       TEXT,
    language    TEXT NOT NULL DEFAULT 'en',
    tier        TEXT,
    active      INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS delivery_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    notification_id TEXT,
    incident_id     TEXT,
    pnr             TEXT,
    passenger       TEXT,
    channel         TEXT NOT NULL,
    recipient       TEXT,
    status          TEXT NOT NULL,
    provider        TEXT,
    detail          TEXT,
    subject         TEXT,
    sent_at         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_delivery_pnr ON delivery_log (pnr, id DESC);

CREATE TABLE IF NOT EXISTS incident_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id TEXT NOT NULL,
    title       TEXT,
    status      TEXT,
    severity    TEXT,
    kind        TEXT,
    location    TEXT,
    logged_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_incident_log ON incident_log (incident_id, id DESC);

CREATE TABLE IF NOT EXISTS crowd_observations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    camera_id       TEXT NOT NULL,
    terminal_id     TEXT NOT NULL,
    observed_at     TEXT NOT NULL,
    people_total    INTEGER NOT NULL,
    people_in_queue INTEGER NOT NULL,
    queue_lanes     INTEGER,
    movement        TEXT,
    confidence      REAL,
    density         REAL,
    level           TEXT,
    wait_min        REAL,
    model           TEXT,
    latency_ms      INTEGER
);
CREATE INDEX IF NOT EXISTS idx_crowd_obs ON crowd_observations (camera_id, id DESC);

CREATE TABLE IF NOT EXISTS crowd_reroutes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    terminal_id   TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    from_camera   TEXT,
    to_camera     TEXT,
    passengers    INTEGER NOT NULL,
    contacts      INTEGER NOT NULL,
    flights       TEXT,
    summary       TEXT,
    delivery      TEXT
);

CREATE TABLE IF NOT EXISTS flight_cache (
    cache_key   TEXT PRIMARY KEY,
    fetched_at  REAL NOT NULL,
    payload     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS api_usage (
    day      TEXT NOT NULL,
    provider TEXT NOT NULL,
    calls    INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (day, provider)
);
"""


def _connect() -> sqlite3.Connection:
    path = Path(settings.database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init() -> None:
    """Create the schema and seed the contact travelers on first use. Safe to call repeatedly."""
    global _ready
    if _ready:
        return
    with _write_lock, closing(_connect()) as conn, conn:
        conn.executescript(SCHEMA)
        existing = {r["pnr"] for r in conn.execute("SELECT pnr FROM contacts")}
        for c in ref.CONTACT_PASSENGERS:
            if c["pnr"] not in existing:
                conn.execute(
                    "INSERT INTO contacts (pnr, first_name, last_name, email, phone, language, tier, active, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)",
                    (c["pnr"], c["first_name"], c["last_name"], c["email"], c["phone"], c["language"], c["tier"], iso(now())),
                )
    _ready = True
    log.info("SQLite ready at %s", settings.database_path)


def _query(sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
    init()
    with closing(_connect()) as conn:
        return conn.execute(sql, tuple(params)).fetchall()


def _write(sql: str, params: Iterable[Any] = ()) -> int:
    init()
    with _write_lock, closing(_connect()) as conn, conn:
        return conn.execute(sql, tuple(params)).lastrowid or 0


def _safe(fn):
    """Persistence is an audit aid: a database problem must never break a recovery workflow."""

    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            log.warning("SQLite %s failed: %s", fn.__name__, exc)
            return None

    wrapper.__name__ = fn.__name__
    return wrapper


# ---- contacts ----------------------------------------------------------------
def load_contacts() -> list[dict]:
    rows = _query("SELECT * FROM contacts WHERE active = 1 ORDER BY created_at, pnr")
    return [{k: r[k] for k in ("pnr", "first_name", "last_name", "email", "phone", "language", "tier")} for r in rows]


# ---- delivery log ------------------------------------------------------------
@_safe
def log_delivery(record: dict, results: list[dict]) -> None:
    stamp = iso(now())
    for r in results:
        _write(
            "INSERT INTO delivery_log (notification_id, incident_id, pnr, passenger, channel, recipient, status, provider, "
            "detail, subject, sent_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (record.get("id"), record.get("incident_id"), record.get("pnr"), record.get("name"), r.get("channel"),
             r.get("to"), r.get("status"),
             r.get("provider") or ("SMTP" if r.get("channel") == "EMAIL" else (settings.sms_provider or None)),
             r.get("detail"), record.get("subject"), stamp),
        )


def recent_deliveries(limit: int = 20, pnr: str | None = None) -> list[dict]:
    sql = "SELECT * FROM delivery_log" + (" WHERE pnr = ?" if pnr else "") + " ORDER BY id DESC LIMIT ?"
    return [dict(r) for r in _query(sql, ([pnr] if pnr else []) + [limit])]


# ---- incidents -----------------------------------------------------------------
@_safe
def log_incident(inc: dict) -> None:
    last = _query("SELECT status FROM incident_log WHERE incident_id = ? ORDER BY id DESC LIMIT 1", (inc["id"],))
    if last and last[0]["status"] == inc.get("status"):
        return
    ev = inc.get("event") or {}
    _write(
        "INSERT INTO incident_log (incident_id, title, status, severity, kind, location, logged_at) VALUES (?,?,?,?,?,?,?)",
        (inc["id"], inc.get("title") or ev.get("title"), inc.get("status"), inc.get("severity"),
         (inc.get("detection") or {}).get("type") or ev.get("kind"), inc.get("location"), iso(now())),
    )


# ---- crowd ---------------------------------------------------------------------
def save_observation(o: dict) -> int:
    return _write(
        "INSERT INTO crowd_observations (camera_id, terminal_id, observed_at, people_total, people_in_queue, queue_lanes, "
        "movement, confidence, density, level, wait_min, model, latency_ms) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (o["camera_id"], o["terminal_id"], o["observed_at"], o["people_total"], o["people_in_queue"], o.get("queue_lanes"),
         o.get("movement"), o.get("confidence"), o.get("density"), o.get("level"), o.get("wait_min"), o.get("model"),
         o.get("latency_ms")),
    )


def recent_observations(camera_id: str, limit: int = 30) -> list[dict]:
    rows = _query("SELECT * FROM crowd_observations WHERE camera_id = ? ORDER BY id DESC LIMIT ?", (camera_id, limit))
    return [dict(r) for r in reversed(rows)]


def save_reroute(entry: dict) -> int:
    return _write(
        "INSERT INTO crowd_reroutes (terminal_id, created_at, from_camera, to_camera, passengers, contacts, flights, summary, "
        "delivery) VALUES (?,?,?,?,?,?,?,?,?)",
        (entry["terminal_id"], iso(now()), entry.get("from_camera"), entry.get("to_camera"), entry["passengers"],
         entry["contacts"], json.dumps(entry.get("flights", [])), entry.get("summary"), json.dumps(entry.get("delivery", {}))),
    )


def recent_reroutes(terminal_id: str | None = None, limit: int = 10) -> list[dict]:
    sql = "SELECT * FROM crowd_reroutes" + (" WHERE terminal_id = ?" if terminal_id else "") + " ORDER BY id DESC LIMIT ?"
    rows = _query(sql, ([terminal_id] if terminal_id else []) + [limit])
    out = []
    for r in rows:
        d = dict(r)
        d["flights"] = json.loads(d["flights"] or "[]")
        d["delivery"] = json.loads(d["delivery"] or "{}")
        out.append(d)
    return out


# ---- flight cache and API usage ---------------------------------------------------
def get_cache(key: str) -> tuple[float, Any] | None:
    rows = _query("SELECT fetched_at, payload FROM flight_cache WHERE cache_key = ?", (key,))
    return (rows[0]["fetched_at"], json.loads(rows[0]["payload"])) if rows else None


def put_cache(key: str, payload: Any) -> None:
    _write("INSERT INTO flight_cache (cache_key, fetched_at, payload) VALUES (?,?,?) "
           "ON CONFLICT(cache_key) DO UPDATE SET fetched_at = excluded.fetched_at, payload = excluded.payload",
           (key, time.time(), json.dumps(payload)))


def count_call(provider: str) -> None:
    day = now().date().isoformat()
    _write("INSERT INTO api_usage (day, provider, calls) VALUES (?,?,1) "
           "ON CONFLICT(day, provider) DO UPDATE SET calls = calls + 1", (day, provider))


def calls_today(provider: str) -> int:
    rows = _query("SELECT calls FROM api_usage WHERE day = ? AND provider = ?", (now().date().isoformat(), provider))
    return rows[0]["calls"] if rows else 0


def calls_this_month(provider: str) -> int:
    rows = _query("SELECT COALESCE(SUM(calls), 0) AS n FROM api_usage WHERE day LIKE ? AND provider = ?",
                  (now().strftime("%Y-%m") + "%", provider))
    return rows[0]["n"]


# ---- summary ------------------------------------------------------------------------
def summary() -> dict:
    tables = ["contacts", "delivery_log", "incident_log", "crowd_observations", "crowd_reroutes", "flight_cache", "api_usage"]
    counts = {t: _query(f"SELECT COUNT(*) AS n FROM {t}")[0]["n"] for t in tables}  # noqa: S608 - fixed table names
    return {"engine": "SQLite", "version": sqlite3.sqlite_version, "path": settings.database_path, "tables": counts}
