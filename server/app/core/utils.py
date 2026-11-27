from __future__ import annotations

import math
from datetime import datetime, timedelta


def now() -> datetime:
    return datetime.now().astimezone()


def iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def parse_dt(value: str | datetime | None) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


def minutes_between(a: datetime, b: datetime) -> int:
    return int((b - a).total_seconds() // 60)


def add_min(dt: datetime, minutes: float) -> datetime:
    return dt + timedelta(minutes=minutes)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def round_to(value: float, step: int = 5) -> int:
    return int(step * round(value / step))


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))
