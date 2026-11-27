"""Public weather feed (Open-Meteo, no API key) with a synthetic fallback for offline demos."""
from __future__ import annotations

import logging
import random

import httpx

from app.config import settings
from app.core.utils import iso, now
from app.data import reference as ref
from app.data.store import store

log = logging.getLogger("arro.weather")

HUBS = ["DEL", "BOM", "BLR", "MAA", "HYD", "CCU"]
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

WMO = {
    0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast", 45: "Fog", 48: "Rime fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Dense drizzle", 61: "Light rain", 63: "Rain", 65: "Heavy rain",
    80: "Rain showers", 81: "Heavy showers", 82: "Violent showers", 95: "Thunderstorm", 96: "Thunderstorm, hail", 99: "Severe thunderstorm",
}


def _record(code: str, temp, wind, gust, precip, vis, wcode, source: str) -> dict:
    return {
        "code": code, "city": ref.AIRPORTS[code]["city"], "temperature_c": temp, "wind_kmh": wind,
        "gust_kmh": gust, "precip_mm": precip, "visibility_m": vis, "weather_code": wcode,
        "condition": WMO.get(wcode, "Cloudy"), "source": source, "observed_at": iso(now()),
        "severe": False,
    }


async def refresh_weather() -> None:
    results: dict[str, dict] = {}
    if settings.weather_api_enabled:
        try:
            params = {
                "latitude": ",".join(str(ref.AIRPORTS[c]["lat"]) for c in HUBS),
                "longitude": ",".join(str(ref.AIRPORTS[c]["lon"]) for c in HUBS),
                "current": "temperature_2m,precipitation,weather_code,wind_speed_10m,wind_gusts_10m,visibility",
                "timezone": "auto",
            }
            async with httpx.AsyncClient(timeout=8) as client:
                resp = await client.get(OPEN_METEO_URL, params=params)
                resp.raise_for_status()
                payload = resp.json()
            payload = payload if isinstance(payload, list) else [payload]
            for code, item in zip(HUBS, payload):
                cur = item.get("current", {})
                results[code] = _record(
                    code, cur.get("temperature_2m"), cur.get("wind_speed_10m"), cur.get("wind_gusts_10m"),
                    cur.get("precipitation"), cur.get("visibility"), cur.get("weather_code", 2), "Open-Meteo")
        except Exception as exc:  # noqa: BLE001
            log.info("Open-Meteo unavailable, using simulated weather: %s", exc)
    rng = random.Random()
    for code in HUBS:
        if code not in results:
            results[code] = _record(code, round(rng.uniform(19, 31), 1), round(rng.uniform(6, 18), 1),
                                    round(rng.uniform(12, 28), 1), 0.0, rng.choice([8000, 10000, 12000]),
                                    rng.choice([0, 1, 2, 3]), "Simulated")
    with store.lock:
        for code, rec in results.items():
            existing = store.weather.get(code)
            if existing and existing.get("severe"):
                continue
            store.weather[code] = rec
