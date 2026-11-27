"""Feed triggers, incident lifecycle, controller decisions and agent graph endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.agents.approval import UPDATE_TYPES
from app.agents.graph import graph_structure
from app.api.operations import incident_summary
from app.api.schemas import DecisionRequest, TriggerRequest, UpdateRequest
from app.data.store import store
from app.services import feeds, orchestrator
from app.services.orchestrator import WorkflowError

router = APIRouter()


@router.get("/feeds/scenarios")
def scenarios():
    return {"items": feeds.scenario_list(),
            "updates": [{"id": k, "label": v["label"], "detail": v["detail"]} for k, v in UPDATE_TYPES.items()]}


@router.get("/feeds/live")
def live_feed(limit: int = Query(50, le=150)):
    with store.lock:
        return {"items": list(store.feed)[:limit]}


@router.post("/feeds/trigger", status_code=201)
def trigger(body: TriggerRequest):
    try:
        incident = orchestrator.trigger_scenario(body.scenario_id)
    except KeyError as exc:
        raise HTTPException(404, "Unknown scenario") from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return incident_summary(incident)


@router.get("/incidents")
def list_incidents():
    with store.lock:
        items = sorted(store.incidents.values(), key=lambda i: i["created_at"], reverse=True)
        return {"items": [incident_summary(i) for i in items]}


@router.get("/incidents/{incident_id}")
def get_incident(incident_id: str):
    with store.lock:
        inc = store.incidents.get(incident_id)
        if not inc:
            raise HTTPException(404, "Incident not found")
        data = {k: v for k, v in inc.items() if not k.startswith("_")}
        if inc.get("work_order_id"):
            data["work_order"] = store.work_orders.get(inc["work_order_id"])
        return data


@router.post("/incidents/{incident_id}/decision", status_code=202)
def decide(incident_id: str, body: DecisionRequest):
    if body.action == "approve" and not body.option_id:
        raise HTTPException(422, "option_id is required to approve")
    decision = body.model_dump()
    if body.preferences:
        decision["preferences"] = body.preferences.model_dump()
    try:
        orchestrator.submit_decision(incident_id, decision)
    except KeyError as exc:
        raise HTTPException(404, "Incident not found") from exc
    except WorkflowError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"status": "accepted"}


@router.post("/incidents/{incident_id}/updates", status_code=202)
def push_update(incident_id: str, body: UpdateRequest):
    try:
        orchestrator.push_update(incident_id, body.update_type, body.controller)
    except KeyError as exc:
        raise HTTPException(404, "Incident not found") from exc
    except WorkflowError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"status": "accepted"}


@router.get("/incidents/{incident_id}/notifications")
def incident_notifications(incident_id: str, outcome: str | None = None, language: str | None = None,
                           q: str | None = None, priority: bool = False,
                           limit: int = Query(50, le=500), offset: int = 0):
    with store.lock:
        rows = [n for n in store.notifications if n["incident_id"] == incident_id]
    if outcome:
        rows = [n for n in rows if n["outcome"] == outcome]
    if language:
        rows = [n for n in rows if n["language_label"] == language]
    if priority:
        rows = [n for n in rows if n["priority"]]
    if q:
        ql = q.lower()
        rows = [n for n in rows if ql in f"{n['pnr']} {n['name']} {n['trip']}".lower()]
    rows.sort(key=lambda n: (not n["priority"], n["name"]))
    return {"total": len(rows), "items": rows[offset:offset + limit]}


@router.get("/agents/graph")
def agents_graph():
    return graph_structure()
