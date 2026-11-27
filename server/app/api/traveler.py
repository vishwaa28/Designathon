"""Traveler self-service: booking lookup, alternatives, rebooking and refunds."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.schemas import RebookRequest, RefundRequest
from app.core.events import bus
from app.core.utils import add_min, iso, now
from app.data import reference as ref
from app.data.store import store

router = APIRouter(prefix="/traveler")


def find_passenger(pnr: str, last_name: str) -> dict:
    pid = store.pnr_index.get(pnr.strip().upper())
    p = store.passengers.get(pid) if pid else None
    if not p or p["last_name"].lower() != last_name.strip().lower():
        raise HTTPException(404, "No booking matches that reference and last name")
    return p


_find = find_passenger


def leg_needs_action(t: dict) -> bool:
    return t["cancelled"] or bool(t["diverted_to"]) or t["delay_min"] >= 30


def actionable_legs(p: dict) -> list[str]:
    legs = [tid for tid in p["legs"] if leg_needs_action(store.trips[tid])]
    if p["status"] in ("REBOOKED", "REFUND_OFFERED", "DIVERTED", "COACH_TRANSFER") and not legs:
        legs = [p["legs"][0]] if p["legs"] else []
    return legs


def _notify(p: dict, subject: str, message: str, outcome: str, trip: str | None, new_trip: str | None) -> dict:
    record = {
        "id": store.next_id("NTF", 100001), "incident_id": None, "pax_id": p["id"], "pnr": p["pnr"],
        "name": f"{p['first_name']} {p['last_name']}", "last_name": p["last_name"], "language": "en",
        "language_label": "English", "channel": p["channel"], "outcome": outcome, "subject": subject,
        "message": message, "priority": False, "escalation": None, "trip": trip, "new_trip": new_trip,
        "status": "DELIVERED", "sent_at": iso(now()), "self_service_url": None,
    }
    store.notifications.append(record)
    return record


def find_alternatives(p: dict, leg_trip_id: str) -> dict:
    """Open-seat services for the same city pair in the next 24 h. Caller holds store.lock."""
    if leg_trip_id not in p["legs"]:
        raise HTTPException(400, "Leg is not part of this booking")
    leg = store.trips[leg_trip_id]
    o_city, d_city = ref.city_of(leg["origin"]), ref.city_of(leg["destination"])
    ready = max(add_min(now(), 30), leg["sched_dep"] if not leg["cancelled"] else add_min(now(), 30))
    horizon = add_min(ready, 24 * 60)
    rows = []
    for t in sorted(store.trips.values(), key=store.est_dep):
        if t["id"] == leg_trip_id or t["cancelled"] or t["diverted_to"]:
            continue
        if ref.city_of(t["origin"]) != o_city or ref.city_of(t["destination"]) != d_city:
            continue
        if not (ready <= store.est_dep(t) <= horizon) or store.spare_seats(t["id"]) <= 0:
            continue
        rows.append({**store.trip_view(t), "seats_left": store.spare_seats(t["id"]),
                     "alt_mode": t["mode"] != leg["mode"]})
    return {"leg": store.trip_view(leg), "items": rows[:8]}


def apply_rebook(p: dict, leg_trip_id: str, new_trip_id: str) -> dict:
    """Move a passenger to another service and record the confirmation. Caller holds store.lock."""
    if leg_trip_id not in p["legs"]:
        raise HTTPException(400, "Leg is not part of this booking")
    new = store.trips.get(new_trip_id)
    if not new or new["cancelled"] or store.spare_seats(new["id"]) <= 0:
        raise HTTPException(409, "Selected service is no longer available")
    old = store.trips[leg_trip_id]
    p["legs"] = [new["id"] if x == old["id"] else x for x in p["legs"]]
    store.pax_by_trip[old["id"]].discard(p["id"])
    store.pax_by_trip[new["id"]].add(p["id"])
    p["status"] = "REBOOKED"
    msg = (f"Confirmed: {p['first_name']}, you are now booked on {new['number']} "
           f"{ref.display_code(new['origin'])}-{ref.display_code(new['destination'])}, departing "
           f"{store.est_dep(new).strftime('%H:%M')}. Your previous booking on {old['number']} is released.")
    return _notify(p, "Rebooking confirmed", msg, "SELF_REBOOKED", old["number"], new["number"])


def apply_refund(p: dict, leg_trip_id: str) -> dict:
    """Cancel a leg and initiate a refund. Caller holds store.lock."""
    if leg_trip_id not in p["legs"]:
        raise HTTPException(400, "Leg is not part of this booking")
    old = store.trips[leg_trip_id]
    p["legs"] = [x for x in p["legs"] if x != old["id"]]
    store.pax_by_trip[old["id"]].discard(p["id"])
    p["status"] = "REFUNDED"
    msg = (f"Refund initiated: INR {p['fare']:,} for {old['number']} will be returned to your original "
           f"payment method within 5-7 working days.")
    return _notify(p, "Refund initiated", msg, "REFUNDED", old["number"], None)


@router.get("/{pnr}")
def lookup(pnr: str, last_name: str):
    with store.lock:
        p = find_passenger(pnr, last_name)
        view = store.pax_view(p)
        notes = sorted((n for n in store.notifications if n["pax_id"] == p["id"]), key=lambda n: n["sent_at"], reverse=True)
        return {"passenger": view, "notifications": notes[:10], "actionable_legs": actionable_legs(p),
                "original_itinerary": [store.trips[t]["number"] for t in p["original_legs"]]}


@router.get("/{pnr}/alternatives")
def alternatives(pnr: str, last_name: str, leg_trip_id: str):
    with store.lock:
        return find_alternatives(find_passenger(pnr, last_name), leg_trip_id)


@router.post("/{pnr}/rebook")
def rebook(pnr: str, body: RebookRequest):
    with store.lock:
        p = find_passenger(pnr, body.last_name)
        record = apply_rebook(p, body.leg_trip_id, body.new_trip_id)
        new = store.trips[body.new_trip_id]
    bus.publish("traveler.rebooked", {"pnr": p["pnr"], "trip": new["number"]})
    return {"status": "rebooked", "notification": record}


@router.post("/{pnr}/refund")
def refund(pnr: str, body: RefundRequest):
    with store.lock:
        p = find_passenger(pnr, body.last_name)
        record = apply_refund(p, body.leg_trip_id)
    bus.publish("traveler.refunded", {"pnr": p["pnr"]})
    return {"status": "refunded", "notification": record}
