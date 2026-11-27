"""Voice assistant endpoints for the traveler portal."""
from __future__ import annotations

from fastapi import APIRouter, WebSocket

from app.services import voice

router = APIRouter(prefix="/voice")


@router.get("/status")
def status():
    return voice.voice_status()


@router.websocket("/ws")
async def voice_socket(ws: WebSocket, pnr: str, name: str, lang: str = "en"):
    await voice.run_session(ws, pnr, name, lang)
