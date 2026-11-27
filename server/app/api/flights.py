"""Real-time flight board (AviationStack) and the database summary."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.data import db
from app.services import aviation

router = APIRouter()


@router.get("/flights/status")
def flights_status():
    return aviation.status()


@router.get("/flights/live")
def flights_live(direction: str = Query("departures", pattern="^(departures|arrivals)$"), refresh: bool = False):
    try:
        return aviation.board(direction, refresh)
    except aviation.AviationError as exc:
        raise HTTPException(exc.status, str(exc)) from None


@router.get("/db/summary")
def db_summary():
    return db.summary()
