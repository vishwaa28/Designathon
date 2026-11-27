"""FastAPI application entry point."""
from __future__ import annotations

import asyncio
import contextlib
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Make `app.*` importable when this file is run directly (python main.py) from inside server/app.
_SERVER_DIR = str(Path(__file__).resolve().parent.parent)
if _SERVER_DIR not in sys.path:
    sys.path.insert(0, _SERVER_DIR)

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware

from app.api import delivery, incidents, operations, stream, traveler, voice
from app.config import settings
from app.services.feeds import telemetry_loop
from app.services.weather import refresh_weather

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


async def _weather_loop() -> None:
    while True:
        await asyncio.sleep(600)
        with contextlib.suppress(Exception):
            await refresh_weather()


@asynccontextmanager
async def lifespan(_: FastAPI):
    await refresh_weather()
    tasks = [asyncio.create_task(telemetry_loop()), asyncio.create_task(_weather_loop())]
    yield
    for t in tasks:
        t.cancel()


app = FastAPI(title=settings.app_name, version=settings.version, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (operations, incidents, traveler, stream, voice, delivery):
    app.include_router(module.router, prefix="/api")


def main() -> None:
    """Run the API server: `python main.py` (from server/ or server/app) or `python -m app.main`."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
