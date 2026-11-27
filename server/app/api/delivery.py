"""E-mail / SMS delivery status, contact passengers, test sends and resends."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.schemas import DeliveryTestRequest
from app.core.utils import iso, now
from app.data.store import store
from app.domain import contacts
from app.domain import notifications as nt
from app.services import delivery

router = APIRouter()


def _contact_view(p: dict) -> dict:
    trip = store.trips[p["legs"][0]] if p["legs"] else None
    last = next((n for n in reversed(store.notifications) if n["pax_id"] == p["id"]), None)
    return {
        "pnr": p["pnr"], "name": f"{p['first_name']} {p['last_name']}", "last_name": p["last_name"],
        "email": delivery.mask_email(p["email"]), "phone": delivery.mask_phone(p["phone"]),
        "status": p["status"], "trip": store.trip_view(trip) if trip else None,
        "last_notification": {k: last.get(k) for k in ("id", "subject", "sent_at", "status", "deliveries", "incident_id")}
        if last else None,
    }


@router.get("/delivery/status")
def delivery_status():
    with store.lock:
        people = [_contact_view(store.passengers[pid]) for pid in contacts.contact_ids()]
    return {**delivery.status(), "contacts": people}


@router.post("/delivery/test")
def delivery_test(body: DeliveryTestRequest):
    with store.lock:
        targets = [dict(store.passengers[pid]) for pid in contacts.contact_ids()
                   if not body.pnr or store.passengers[pid]["pnr"] == body.pnr.upper()]
    if not targets:
        raise HTTPException(404, "No contact passenger with that booking reference")
    results = []
    for p in targets:
        message = (f"Hello {p['first_name']}, this is a test message from the Meridian Airways disruption desk. "
                   f"Alerts for booking {p['pnr']} will reach you here.")
        record = {"name": f"{p['first_name']} {p['last_name']}", "pnr": p["pnr"], "subject": "Notification test",
                  "message": message, "self_service_url": nt.portal_link(p["pnr"], p["last_name"])}
        pax = {**p, "email": p["email"] if "EMAIL" in body.channels else None,
               "phone": p["phone"] if "SMS" in body.channels else None}
        delivery.deliver(record, pax)
        results.append({"pnr": p["pnr"], "name": record["name"], "status": record["status"],
                        "deliveries": record["deliveries"]})
    return {"sent_at": iso(now()), "results": results}


@router.post("/notifications/{notification_id}/resend")
def resend(notification_id: str):
    with store.lock:
        record = next((n for n in store.notifications if n["id"] == notification_id), None)
        if record is None:
            raise HTTPException(404, "Notification not found")
        p = dict(store.passengers[record["pax_id"]])
    if not p.get("contact"):
        raise HTTPException(409, "This traveler has no verified e-mail or mobile number")
    delivery.deliver(record, p)
    return record
