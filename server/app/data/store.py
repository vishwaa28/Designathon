"""In-memory operational data store.

All mutable state lives here behind a re-entrant lock so that LangGraph worker threads and
API handlers can share it safely. Swapping this for a database-backed repository only
requires re-implementing the public methods.
"""
from __future__ import annotations

import random
import threading
from collections import deque
from datetime import datetime

from app.core.utils import add_min, iso, now
from app.data import reference as ref
from app.data import seed

TIER_RANK = {"PLATINUM": 3, "GOLD": 2, "SILVER": 1, None: 0}
PRIORITY_SSR = {"WCHR", "UMNR", "MEDA"}


def is_priority(p: dict) -> bool:
    return p.get("ssr") in PRIORITY_SSR or p.get("tier") in ("PLATINUM", "GOLD")


def priority_score(p: dict) -> int:
    score = TIER_RANK.get(p.get("tier"), 0)
    if p.get("ssr") in PRIORITY_SSR:
        score += 10
    elif p.get("ssr") == "SRCT":
        score += 2
    return score


class Store:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.reset()

    def reset(self) -> None:
        with self.lock:
            data = seed.generate(now())
            self.base: datetime = data["base"]
            self.trips: dict[str, dict] = data["trips"]
            self.rotations: dict[str, list[str]] = data["rotations"]
            self.vehicles: dict[str, dict] = data["vehicles"]
            self.crew: dict[str, dict] = data["crew"]
            self.pairings: dict[str, dict] = data["pairings"]
            self.reserves: dict[str, dict[str, list[str]]] = data["reserves"]
            self.passengers: dict[str, dict] = data["passengers"]
            self.pax_by_trip: dict[str, set[str]] = data["pax_by_trip"]
            self.assets: dict[str, dict] = data["assets"]
            self.teams: dict[str, dict] = data["teams"]
            self.pnr_index = {p["pnr"]: pid for pid, p in self.passengers.items()}
            self.incidents: dict[str, dict] = {}
            self.work_orders: dict[str, dict] = {}
            self.notifications: list[dict] = []
            self.plan_artifacts: dict[str, dict] = {}
            self.seat_assignments: dict[str, dict[str, str]] = {}
            self.feed: deque[dict] = deque(maxlen=150)
            self.weather: dict[str, dict] = {}
            self._counters: dict[str, int] = {}

    def next_id(self, prefix: str, start: int = 1001) -> str:
        with self.lock:
            n = self._counters.get(prefix, start)
            self._counters[prefix] = n + 1
            return f"{prefix}-{n}"

    # ---- Trips -----------------------------------------------------------
    def est_dep(self, t: dict) -> datetime:
        return add_min(t["sched_dep"], t["delay_min"])

    def est_arr(self, t: dict) -> datetime:
        return add_min(t["sched_arr"], t["delay_min"])

    def trip_status(self, t: dict, ref_time: datetime | None = None) -> str:
        ref_time = ref_time or now()
        if t["cancelled"]:
            return "CANCELLED"
        if t["diverted_to"]:
            return "DIVERTED"
        if ref_time >= self.est_arr(t):
            return "ARRIVED"
        if ref_time >= self.est_dep(t):
            return "EN_ROUTE"
        if t["delay_min"] >= 15:
            return "DELAYED"
        if (self.est_dep(t) - ref_time).total_seconds() <= 45 * 60:
            return "BOARDING"
        return "ON_TIME"

    def booked(self, trip_id: str) -> int:
        return len(self.pax_by_trip.get(trip_id, ()))

    def spare_seats(self, trip_id: str) -> int:
        t = self.trips[trip_id]
        return max(0, t["capacity"] - self.booked(trip_id))

    # ---- Seats -----------------------------------------------------------
    def seat_layout(self, trip_id: str) -> tuple[list[list[str]], str]:
        """Cabin layout as rows of seat ids (3-3 for jets, 2-2 for turboprops) plus the letters used."""
        t = self.trips[trip_id]
        letters = "ABCD" if t["vehicle_type"].startswith("ATR") else "ABCDEF"
        rows: list[list[str]] = []
        n, row = 0, 1
        while n < t["capacity"]:
            seats = [f"{row}{letter}" for letter in letters[: t["capacity"] - n]]
            rows.append(seats)
            n += len(seats)
            row += 1
        return rows, letters

    def seat_status(self, trip_id: str, pax_id: str | None = None) -> dict[str, str]:
        """Seat id -> free | taken | mine. Occupancy is deterministic per trip; chosen seats are tracked explicitly."""
        rows, _ = self.seat_layout(trip_id)
        all_seats = [s for r in rows for s in r]
        assigned = self.seat_assignments.get(trip_id, {})
        others = [s for s in all_seats if s not in assigned]
        random.Random(trip_id).shuffle(others)
        taken = set(others[: max(0, self.booked(trip_id) - len(assigned))])
        status = {}
        for s in all_seats:
            if s in assigned:
                status[s] = "mine" if assigned[s] == pax_id else "taken"
            else:
                status[s] = "taken" if s in taken else "free"
        return status

    def seat_map(self, trip_id: str, pax_id: str | None = None) -> dict:
        rows, letters = self.seat_layout(trip_id)
        status = self.seat_status(trip_id, pax_id)
        return {
            "trip": self.trip_view(self.trips[trip_id]),
            "letters": list(letters),
            "aisle_after": len(letters) // 2,
            "rows": [{"row": int(r[0][:-1]), "seats": [{"id": s, "status": status[s]} for s in r]} for r in rows],
            "free": sum(1 for v in status.values() if v == "free"),
        }

    def assign_seat(self, trip_id: str, pax_id: str, seat: str | None = None) -> str | None:
        """Give the passenger a seat on the trip (the requested one, or the first free window seat)."""
        status = self.seat_status(trip_id, pax_id)
        if seat is not None:
            if status.get(seat) != "free":
                return None
        else:
            free = [s for s, v in status.items() if v == "free"]
            if not free:
                return None
            windows = [s for s in free if s[-1] in "AFD"]
            seat = (windows or free)[0]
        self.seat_assignments.setdefault(trip_id, {})[seat] = pax_id
        return seat

    def release_seat(self, trip_id: str, pax_id: str) -> None:
        held = self.seat_assignments.get(trip_id, {})
        for s in [s for s, pid in held.items() if pid == pax_id]:
            del held[s]

    def trip_view(self, t: dict, ref_time: datetime | None = None) -> dict:
        return {
            "id": t["id"],
            "number": t["number"],
            "name": t["name"],
            "operator": t["operator"],
            "origin": ref.display_code(t["origin"]),
            "destination": ref.display_code(t["destination"]),
            "origin_city": ref.city_of(t["origin"]),
            "destination_city": ref.city_of(t["destination"]),
            "route": [ref.display_code(s) for s in t["route"]],
            "sched_dep": iso(t["sched_dep"]),
            "sched_arr": iso(t["sched_arr"]),
            "est_dep": iso(self.est_dep(t)),
            "est_arr": iso(self.est_arr(t)),
            "delay_min": t["delay_min"],
            "status": self.trip_status(t, ref_time),
            "vehicle_id": t["vehicle_id"],
            "vehicle_type": t["vehicle_type"],
            "capacity": t["capacity"],
            "booked": self.booked(t["id"]),
            "load_factor": round(self.booked(t["id"]) / t["capacity"], 3),
            "gate": t["gate"],
            "diverted_to": ref.display_code(t["diverted_to"]) if t["diverted_to"] else None,
            "disruption_ids": list(t["disruption_ids"]),
            "remarks": t["remarks"],
        }

    # ---- Passengers ------------------------------------------------------
    def pax_view(self, p: dict, include_legs: bool = True) -> dict:
        view = {
            "id": p["id"],
            "pnr": p["pnr"],
            "name": f"{p['first_name']} {p['last_name']}",
            "first_name": p["first_name"],
            "last_name": p["last_name"],
            "tier": p["tier"],
            "ssr": p["ssr"],
            "language": p["language"],
            "language_label": ref.LANGUAGES.get(p["language"], p["language"]),
            "channel": p["channel"],
            "cabin": p["cabin"],
            "status": p["status"],
            "priority": is_priority(p),
            "contact": bool(p.get("contact")),
        }
        if include_legs:
            view["legs"] = [self.trip_view(self.trips[t]) | {"seat": self._seat_of(p, t)} for t in p["legs"]]
        return view

    def _seat_of(self, p: dict, trip_id: str) -> str | None:
        for s, pid in self.seat_assignments.get(trip_id, {}).items():
            if pid == p["id"]:
                return s
        return None

    def crew_view(self, cid: str) -> dict:
        c = self.crew[cid]
        return {**c, "role_label": ref.ROLE_LABELS.get(c["role"], c["role"]), "base": ref.display_code(c["base"])}

    # ---- Assets ----------------------------------------------------------
    def asset_view(self, a: dict) -> dict:
        return {
            "id": a["id"],
            "name": a["name"],
            "type": a["type"],
            "category": a["category"],
            "location": ref.display_code(a["location"]),
            "criticality": a["criticality"],
            "health": a["health"],
            "status": a["status"],
            "metrics": a["metrics"],
            "baseline": a["baseline"],
            "last_inspection": iso(a["last_inspection"]),
        }

    def add_feed(self, item: dict) -> dict:
        with self.lock:
            self.feed.appendleft(item)
        return item


store = Store()
