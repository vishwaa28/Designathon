"""FastAPI application entry point."""
from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
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
