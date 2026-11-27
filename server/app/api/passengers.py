"""Passenger directory over the live booking store (contact travelers are flagged)."""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.data import db
from app.data.store import store
from app.services import delivery

router = APIRouter()


@router.get("/passengers")
def passengers(q: str = "", contact: bool | None = None, limit: int = Query(50, ge=1, le=200)):
    needle = q.strip().lower()
    rows = []
    with store.lock:
        for p in store.passengers.values():
            is_contact = bool(p.get("contact"))
            if contact is not None and is_contact != contact:
                continue
            name = f"{p['first_name']} {p['last_name']}"
            if needle and needle not in name.lower() and needle not in p["pnr"].lower():
                continue
            trip = store.trips[p["legs"][0]] if p["legs"] else None
            rows.append({
                "pnr": p["pnr"], "name": name, "contact": is_contact, "status": p["status"], "tier": p["tier"],
                "language": p["language"],
                "email": delivery.mask_email(p["email"]) if is_contact else None,
                "phone": delivery.mask_phone(p["phone"]) if is_contact else None,
                "trip": trip["number"] if trip else None, "route": f"{trip['origin']} to {trip['destination']}" if trip else None,
            })
    rows.sort(key=lambda r: (not r["contact"], r["name"]))
    return {"count": len(rows), "total": len(store.passengers), "items": rows[:limit]}


@router.get("/contacts")
def contacts():
    """Contact travelers as stored in SQLite (e-mail and phone masked)."""
    return {"items": [
        {"pnr": c["pnr"], "name": f"{c['first_name']} {c['last_name']}", "email": delivery.mask_email(c["email"]),
         "phone": delivery.mask_phone(c["phone"]), "language": c["language"], "tier": c["tier"]}
        for c in db.load_contacts()]}


@router.get("/delivery/log")
def delivery_log(limit: int = Query(20, ge=1, le=200), pnr: str | None = None):
    return {"items": db.recent_deliveries(limit, pnr.upper() if pnr else None)}
