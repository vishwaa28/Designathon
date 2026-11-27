"""Crowd monitor endpoints: camera frames in, terminal totals, queue estimates and reroute advisories out."""
from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException

from app.api.schemas import FrameRequest, RerouteRequest
from app.services import crowd

router = APIRouter(prefix="/crowd")

_DATA_URL = re.compile(r"^data:(image/(?:jpeg|png|webp));base64,", re.I)


def _wrap(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except crowd.CrowdError as exc:
        raise HTTPException(exc.status, str(exc)) from None


@router.get("/overview")
def overview():
    return crowd.overview()


@router.get("/terminals/{terminal_id}/plan")
def plan(terminal_id: str):
    return _wrap(crowd.plan, terminal_id)


@router.post("/cameras/{camera_id}/frame")
def analyze(camera_id: str, body: FrameRequest):
    image, mime = body.image, "image/jpeg"
    if m := _DATA_URL.match(image):
        mime, image = m.group(1).lower(), image[m.end():]
    return _wrap(crowd.analyze_frame, camera_id, image, mime)


@router.post("/terminals/{terminal_id}/reroute")
def reroute(terminal_id: str, body: RerouteRequest):
    return _wrap(crowd.send_reroute, terminal_id, body.force)
