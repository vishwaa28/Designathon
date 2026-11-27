"""Server-sent events stream of agent, incident and feed events."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.core.events import bus

router = APIRouter()


@router.get("/stream")
async def stream(request: Request):
    last_header = request.headers.get("last-event-id")
    last_id = int(last_header) if last_header and last_header.isdigit() else bus.last_id

    async def generator():
        nonlocal last_id
        yield "retry: 3000\n\n"
        idle = 0.0
        while True:
            if await request.is_disconnected():
                break
            events = bus.since(last_id)
            for e in events:
                last_id = e["id"]
                yield f"id: {e['id']}\nevent: message\ndata: {json.dumps(e, default=str)}\n\n"
            if events:
                idle = 0.0
            else:
                idle += 0.35
                if idle >= 15:
                    idle = 0.0
                    yield ": keep-alive\n\n"
            await asyncio.sleep(0.35)

    return StreamingResponse(generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
