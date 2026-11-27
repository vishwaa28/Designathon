"""Dashboard, schedule, assets, work orders and simulation endpoints."""
from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, HTTPException, Query

from app.api.schemas import ProviderUpdate, WorkOrderPatch
from app.core.events import bus
from app.core.llm import llm
from app.core.utils import add_min, iso, now
from app.data import reference as ref
from app.data.store import store
from app.services.weather import refresh_weather

router = APIRouter()

ACTIVE = {"DETECTING", "ANALYZING", "PLANNING", "AWAITING_APPROVAL", "PROCESSING", "REPLANNING", "EXECUTING"}
HUB_NODES = ["MAA", "R:MAS", "R:MS", "BLR", "HYD", "CJB", "COK", "R:SBC"]
CITY_AIRPORT = {"R:MAS": "MAA", "R:MS": "MAA", "R:SBC": "BLR"}


@router.get("/health")
def health():
    return {"status": "ok", "time": iso(now()), "llm": llm.status()["active"]}


@router.get("/settings/llm")
def get_llm():
    return llm.status()


@router.put("/settings/llm")
def set_llm(body: ProviderUpdate):
    try:
        llm.set_active(body.provider)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    bus.publish("settings.updated", llm.status())
    return llm.status()


@router.post("/simulation/reset")
async def reset_simulation():
    store.reset()
    await refresh_weather()
    bus.publish("simulation.reset", {})
    return {"status": "reset", "base": iso(store.base)}


@router.get("/dashboard")
def dashboard():
    ref_time = now()
    with store.lock:
        trips = list(store.trips.values())
        statuses = Counter(store.trip_status(t, ref_time) for t in trips)
        live = [t for t in trips if not t["cancelled"]]
        on_time = sum(1 for t in live if t["delay_min"] < 15)
        incidents = list(store.incidents.values())
        active = [i for i in incidents if i["status"] in ACTIVE]
        disrupted_nodes = set()
        for i in active:
            ev = i["event"]
            disrupted_nodes.add(ev["location"])
            for c in ev.get("corridor") or []:
                disrupted_nodes.add(c)

        hubs = []
        for node in HUB_NODES:
            window_end = add_min(ref_time, 180)
            moves = [t for t in trips if (t["origin"] == node and ref_time <= store.est_dep(t) <= window_end)
                     or (t["destination"] == node and ref_time <= store.est_arr(t) <= window_end)]
            delayed = sum(1 for t in moves if t["delay_min"] >= 15 and not t["cancelled"])
            cancelled = sum(1 for t in moves if t["cancelled"])
            hubs.append({
                "code": ref.display_code(node), "city": ref.city_of(node), "mode": "TRAIN" if node.startswith("R:") else "FLIGHT",
                "name": ref.place(node)["name"], "movements_3h": len(moves), "delayed": delayed, "cancelled": cancelled,
                "status": "DISRUPTED" if node in disrupted_nodes else ("STRAINED" if delayed >= 3 else "NORMAL"),
                "weather": store.weather.get(node) or store.weather.get(CITY_AIRPORT.get(node, "")),
            })

        hourly = []
        start = add_min(store.base, -180)
        for h in range(19):
            h0, h1 = add_min(start, h * 60), add_min(start, (h + 1) * 60)
            deps = [t for t in trips if h0 <= t["sched_dep"] < h1]
            hourly.append({
                "hour": h0.strftime("%H:%M"),
                "flights": sum(1 for t in deps if t["mode"] == "FLIGHT"),
                "trains": sum(1 for t in deps if t["mode"] == "TRAIN"),
                "delayed": sum(1 for t in deps if t["delay_min"] >= 15 and not t["cancelled"]),
                "cancelled": sum(1 for t in deps if t["cancelled"]),
            })
        pax_affected = sum((i.get("impact") or {}).get("summary", {}).get("pax_affected", 0) for i in active)
        open_wos = sum(1 for w in store.work_orders.values() if w["status"] != "COMPLETED")
        recent = sorted(incidents, key=lambda i: i["created_at"], reverse=True)[:6]
        return {
            "generated_at": iso(ref_time),
            "kpis": {
                "trips_total": len(trips),
                "flights": sum(1 for t in trips if t["mode"] == "FLIGHT"),
                "trains": sum(1 for t in trips if t["mode"] == "TRAIN"),
                "on_time_pct": round(100 * on_time / max(1, len(live)), 1),
                "delayed": sum(1 for t in live if t["delay_min"] >= 15),
                "cancelled": sum(1 for t in trips if t["cancelled"]),
                "passengers": len(store.passengers),
                "active_incidents": len(active),
                "awaiting_approval": sum(1 for i in active if i["status"] == "AWAITING_APPROVAL"),
                "pax_affected": pax_affected,
                "open_work_orders": open_wos,
                "notifications_sent": len(store.notifications),
            },
            "status_counts": dict(statuses),
            "hubs": hubs,
            "hourly": hourly,
            "recent_incidents": [incident_summary(i) for i in recent],
            "feed": list(store.feed)[:25],
        }


def incident_summary(i: dict) -> dict:
    impact = (i.get("impact") or {}).get("summary") or {}
    rec = i.get("recommendation") or {}
    return {
        "id": i["id"], "title": i["title"], "category": i["category"], "mode": i["mode"],
        "severity": i["severity"], "status": i["status"], "location": i["location"],
        "created_at": i["created_at"], "updated_at": i["updated_at"], "resolved_at": i.get("resolved_at"),
        "plan_version": i["plan_version"], "pax_affected": impact.get("pax_affected"),
        "trips_affected": (impact.get("trips_direct") or 0) + (impact.get("trips_cascade") or 0) if impact else None,
        "recommended": rec.get("option_id"), "work_order_id": i.get("work_order_id"),
        "decision": (i.get("decision") or {}).get("action"),
    }


@router.get("/trips")
def list_trips(mode: str | None = None, status: str | None = None, q: str | None = None,
               disrupted: bool = False, limit: int = Query(200, le=500)):
    ref_time = now()
    with store.lock:
        rows = [store.trip_view(t, ref_time) for t in sorted(store.trips.values(), key=lambda t: t["sched_dep"])]
    if mode:
        rows = [r for r in rows if r["mode"] == mode.upper()]
    if status:
        rows = [r for r in rows if r["status"] == status.upper()]
    if disrupted:
        rows = [r for r in rows if r["disruption_ids"] or r["delay_min"] >= 15 or r["status"] == "CANCELLED"]
    if q:
        ql = q.lower()
        rows = [r for r in rows if ql in f"{r['number']} {r['origin']} {r['destination']} {r['origin_city']} {r['destination_city']} {r['vehicle_id']}".lower()]
    return {"total": len(rows), "items": rows[:limit]}


@router.get("/trips/{trip_id}")
def get_trip(trip_id: str):
    with store.lock:
        t = store.trips.get(trip_id)
        if not t:
            raise HTTPException(404, "Trip not found")
        pax_ids = sorted(store.pax_by_trip[trip_id], key=lambda pid: store.passengers[pid]["last_name"])
        pax = [store.pax_view(store.passengers[pid], include_legs=False) | {
            "connection": len(store.passengers[pid]["legs"]) > 1,
            "itinerary": [store.trips[x]["number"] for x in store.passengers[pid]["legs"]]} for pid in pax_ids]
        pairing = store.pairings.get(t["pairing_id"])
        crew = [store.crew_view(cid) for cid in pairing["crew_ids"]] if pairing else []
        rotation = [store.trip_view(store.trips[x]) for x in store.rotations.get(t["vehicle_id"], [])]
        duty = None
        if pairing:
            last = store.trips[pairing["trip_ids"][-1]]
            duty = {"start": iso(pairing["duty_start"]),
                    "projected_end": iso(add_min(store.est_arr(last), 30)),
                    "projected_h": round((add_min(store.est_arr(last), 30) - pairing["duty_start"]).total_seconds() / 3600, 2),
                    "trips": [store.trips[x]["number"] for x in pairing["trip_ids"]]}
        return {
            "trip": store.trip_view(t), "crew": crew, "duty": duty, "rotation": rotation,
            "passengers": pax[:400], "passenger_count": len(pax),
            "summary": {
                "priority": sum(1 for p in pax if p["priority"]),
                "connections": sum(1 for p in pax if p["connection"]),
                "tiers": dict(Counter(p["tier"] for p in pax if p["tier"])),
                "ssr": dict(Counter(p["ssr"] for p in pax if p["ssr"])),
            },
        }


@router.get("/assets")
def list_assets():
    with store.lock:
        items = [store.asset_view(a) for a in store.assets.values()]
        teams = [{**t, "base": ref.display_code(t["base"])} for t in store.teams.values()]
    order = {"OUT_OF_SERVICE": 0, "DEGRADED": 1, "MAINTENANCE": 2, "OPERATIONAL": 3}
    items.sort(key=lambda a: (order.get(a["status"], 9), a["category"] in ("Fleet", "Rolling stock"), a["health"]))
    return {"items": items, "teams": teams}


@router.get("/work-orders")
def list_work_orders():
    with store.lock:
        items = sorted(store.work_orders.values(), key=lambda w: w["created_at"], reverse=True)
        return {"items": items}


@router.patch("/work-orders/{wo_id}")
def patch_work_order(wo_id: str, body: WorkOrderPatch):
    with store.lock:
        wo = store.work_orders.get(wo_id)
        if not wo:
            raise HTTPException(404, "Work order not found")
        wo["status"] = body.status
        wo["updated_at"] = iso(now())
        if body.status == "COMPLETED":
            wo["completed_at"] = iso(now())
            asset = store.assets.get(wo["asset_id"])
            if asset:
                asset["status"] = "OPERATIONAL"
                asset["metrics"] = dict(asset["baseline"])
                asset["health"] = 92
            team = store.teams.get(wo["team"]["id"])
            if team:
                team["status"] = "AVAILABLE"
    bus.publish("work_order.updated", {"id": wo_id, "status": body.status})
    return wo
