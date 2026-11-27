from functools import lru_cache

from app.core.utils import haversine_km, round_to
from app.data import reference as ref


@lru_cache(maxsize=512)
def segment_km(a: str, b: str) -> float:
    pa, pb = ref.place(a), ref.place(b)
    return haversine_km(pa["lat"], pa["lon"], pb["lat"], pb["lon"]) * 1.25


@lru_cache(maxsize=512)
def flight_minutes(a: str, b: str) -> int:
    pa, pb = ref.place(a), ref.place(b)
    return round_to(35 + haversine_km(pa["lat"], pa["lon"], pb["lat"], pb["lon"]) / 780 * 60)
