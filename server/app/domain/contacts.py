"""Contact travelers: real people (e-mail and mobile) who hold a booking on every flight.

Each contact has one booking per flight (see ``data/seed.py``) so any disruption finds them on the manifest. Their
original booking reference is the *primary* record; bookings on the other flights have derived references.
Real e-mail and SMS are sent for one booking per person per run, so four people do not receive dozens of messages
when an incident touches many flights. The other bookings still get a notification record and can be re-sent by hand.
"""
from __future__ import annotations

from app.data.store import store
from app.domain import network


def contact_key(p: dict) -> str:
    return p.get("contact_key") or p["pnr"]


def contact_ids() -> list[str]:
    """One passenger id per contact person (their primary booking)."""
    return [pid for pid, p in store.passengers.items() if p.get("contact") and p["pnr"] == contact_key(p)]


def all_contact_ids() -> list[str]:
    """Every contact booking, across all flights."""
    return [pid for pid, p in store.passengers.items() if p.get("contact")]


def earliest_per_contact(pids=None, trip_ids: set[str] | None = None) -> list[str]:
    """For each contact person, the booking on the soonest departure (optionally limited to ``trip_ids``). Caller holds store.lock."""
    best: dict[str, tuple] = {}
    for pid in (all_contact_ids() if pids is None else pids):
        p = store.passengers[pid]
        if not p.get("contact") or not p["legs"]:
            continue
        tid = p["legs"][0]
        if trip_ids is not None and tid not in trip_ids:
            continue
        dep = store.est_dep(store.trips[tid])
        key = contact_key(p)
        if key not in best or dep < best[key][0]:
            best[key] = (dep, pid)
    return [pid for _, pid in sorted(best.values(), key=lambda x: x[0])]


def attach(scope: dict) -> list[dict]:
    """Report, per contact person, the soonest affected flight they are booked on. Caller holds store.lock."""
    primary = network.primary_delays(scope)
    placed = []
    for pid in earliest_per_contact(trip_ids=set(primary)):
        p = store.passengers[pid]
        trip = store.trips[p["legs"][0]]
        placed.append({"pnr": p["pnr"], "name": f"{p['first_name']} {p['last_name']}", "trip": trip["number"],
                       "trip_id": trip["id"]})
    return placed
