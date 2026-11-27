"""Real-time flight board from the AviationStack API.

* Results are cached in SQLite (``flight_cache``) for ``AVIATIONSTACK_CACHE_SECONDS`` because the free plan is
  metered (about 100 calls a month) and survives server restarts.
* If a refresh fails (quota, network) the last cached board is served and marked ``stale-cache``.
* AviationStack labels local airport times with ``+00:00``; they are re-labelled here with the real Indian offset.
* Codeshare duplicates are dropped so each physical flight appears once, under its operating carrier.
"""
from __future__ import annotations

import logging
import time
from collections import Counter
from datetime import datetime, timedelta, timezone

import httpx

from app.config import settings
from app.core.utils import iso, now
from app.data import db

log = logging.getLogger("arro.aviation")

LOCAL_TZ = timezone(timedelta(hours=5, minutes=30))   # Indian Standard Time, the zone of every airport served
MIN_REFRESH_S = 60                                      # manual refresh is ignored if the cache is younger than this
TIMEOUT_S = 20
DIRECTIONS = {"departures": "dep_iata", "arrivals": "arr_iata"}


class AviationError(Exception):
    def __init__(self, message: str, status: int = 502) -> None:
        super().__init__(message)
        self.status = status


def configured() -> bool:
    return bool(settings.aviationstack_key)


def status() -> dict:
    return {
        "configured": configured(), "provider": "AviationStack", "airport": settings.aviationstack_airport,
        "cache_ttl_s": settings.aviationstack_cache_s,
        "calls_today": db.calls_today("aviationstack"), "calls_this_month": db.calls_this_month("aviationstack"),
    }


def _local(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts[:19]).replace(tzinfo=LOCAL_TZ)
    except ValueError:
        return None


def _item(d: dict, direction: str) -> dict | None:
    flight = d.get("flight") or {}
    if flight.get("codeshared"):
        return None
    dep, arr = d.get("departure") or {}, d.get("arrival") or {}
    own, other = (dep, arr) if direction == "departures" else (arr, dep)
    sched, est, actual = _local(own.get("scheduled")), _local(own.get("estimated")), _local(own.get("actual"))
    if sched is None:
        return None
    live = d.get("live") or {}
    airline = d.get("airline") or {}
    aircraft = d.get("aircraft") or {}
    return {
        "flight": flight.get("iata") or flight.get("icao") or "",
        "airline": airline.get("name"),
        "status": (d.get("flight_status") or "unknown").lower(),
        "terminal": own.get("terminal"), "gate": own.get("gate"), "baggage": own.get("baggage"),
        "delay_min": own.get("delay") or 0,
        "scheduled": iso(sched), "estimated": iso(est or sched), "actual": iso(actual),
        "other": {"iata": other.get("iata"), "airport": other.get("airport")},
        "aircraft": aircraft.get("iata") or aircraft.get("icao"), "registration": aircraft.get("registration"),
        "live": {
            "latitude": live.get("latitude"), "longitude": live.get("longitude"),
            "altitude_m": round(live["altitude"]) if live.get("altitude") is not None else None,
            "speed_kmh": round(live["speed_horizontal"]) if live.get("speed_horizontal") is not None else None,
            "heading": live.get("direction"), "on_ground": live.get("is_ground"), "updated": live.get("updated"),
        } if live.get("latitude") is not None else None,
    }


def _fetch(direction: str) -> list[dict]:
    key = settings.aviationstack_key
    params = {"access_key": key, DIRECTIONS[direction]: settings.aviationstack_airport, "limit": 100}
    try:
        resp = httpx.get(f"{settings.aviationstack_base}/flights", params=params, timeout=TIMEOUT_S)
        body = resp.json()
    except Exception as exc:  # noqa: BLE001
        # Never include the exception text verbatim: some transport errors echo the request URL (and the key).
        raise AviationError(f"Could not reach AviationStack ({type(exc).__name__}).") from None
    db.count_call("aviationstack")
    if isinstance(body, dict) and body.get("error"):
        err = body["error"]
        code = err.get("code", "error")
        msg = str(err.get("message") or code).replace(key or "", "***")
        raise AviationError(f"AviationStack: {code}. {msg}", 429 if "limit" in str(code) else 502)
    rows = [i for i in (_item(d, direction) for d in body.get("data", [])) if i]
    rows.sort(key=lambda r: r["estimated"])
    return rows


def board(direction: str, refresh: bool = False) -> dict:
    if direction not in DIRECTIONS:
        raise AviationError("direction must be departures or arrivals", 400)
    key = f"{direction}:{settings.aviationstack_airport}"
    cached = db.get_cache(key)
    age = (time.time() - cached[0]) if cached else None
    fresh = cached is not None and age < settings.aviationstack_cache_s
    if refresh and cached is not None and age < MIN_REFRESH_S:
        fresh = True
    source, error, items = "cache", None, (cached[1] if cached else [])
    if not fresh:
        if not configured():
            if not cached:
                raise AviationError("AviationStack is not configured. Set AVIATIONSTACK_API_KEY.", 503)
            source, error = "stale-cache", "AviationStack key not configured"
        else:
            try:
                items = _fetch(direction)
                db.put_cache(key, items)
                source, age = "live", 0.0
            except AviationError as exc:
                if not cached:
                    raise
                source, error = "stale-cache", str(exc)
                log.warning("AviationStack refresh failed, serving cache: %s", exc)
    counts = Counter(i["status"] for i in items)
    return {
        "direction": direction, "airport": settings.aviationstack_airport, "source": source, "error": error,
        "fetched_at": iso(datetime.fromtimestamp(time.time() - (age or 0), tz=LOCAL_TZ)) if age is not None else iso(now()),
        "age_s": int(age or 0), "cache_ttl_s": settings.aviationstack_cache_s, "count": len(items),
        "by_status": dict(counts), "terminals": dict(Counter(i["terminal"] or "n/a" for i in items)),
        "items": items,
    }
