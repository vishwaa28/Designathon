"""Passengers with real contact details, kept on the services hit by every disruption."""
from __future__ import annotations

from app.core.utils import add_min, now
from app.data.store import store
from app.domain import network

PER_TRIP = 2


def contact_ids() -> list[str]:
    return [pid for pid, p in store.passengers.items() if p.get("contact")]


def _candidates(scope: dict, primary: dict[str, int]) -> list[str]:
    soon = add_min(now(), 5)
    rows = [tid for tid, d in primary.items() if d >= 30 and store.est_dep(store.trips[tid]) >= soon]
    if scope["type"] == "AIRPORT_CLOSURE":
        departures = [tid for tid in rows if store.trips[tid]["origin"] == scope["node"]]
        rows = departures or rows
    return sorted(rows, key=lambda tid: store.est_dep(store.trips[tid]))


def attach(scope: dict) -> list[dict]:
    """Book each contact passenger onto an affected service (two per service). Caller holds store.lock."""
    primary = network.primary_delays(scope)
    targets = _candidates(scope, primary)
    if not targets:
        return []
    placed = []
    for i, pid in enumerate(contact_ids()):
        p = store.passengers[pid]
        if not any(tid in primary for tid in p["legs"]):
            target = targets[min(i // PER_TRIP, len(targets) - 1)]
            for old in p["legs"]:
                store.pax_by_trip[old].discard(pid)
            p["legs"] = [target]
            p["original_legs"] = [target]
            p["status"] = "CONFIRMED"
            store.pax_by_trip[target].add(pid)
        trip = store.trips[p["legs"][0]]
        placed.append({"pnr": p["pnr"], "name": f"{p['first_name']} {p['last_name']}", "trip": trip["number"],
                       "trip_id": trip["id"]})
    return placed
