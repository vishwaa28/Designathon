from __future__ import annotations

import json

from app.agents.runtime import agent_node, update_incident
from app.core.events import bus
from app.core.llm import llm
from app.core.utils import iso, now
from app.data.store import store
from app.domain import triage

SYSTEM = ("You are an infrastructure maintenance planner for airports and railways. Write precise work orders "
          "for field technicians: what failed, what to check first, and the safety precautions.")


@agent_node("infra_triage")
def infra_node(state: dict) -> tuple[dict, dict]:
    det = state["detection"]
    event = state["event"]
    incident_id = state["incident_id"]
    asset = store.assets[event["asset_id"]]
    result = triage.triage(asset, det, state.get("adjustments"))

    prompt = (
        f"Asset: {json.dumps(result['asset'], default=str)}\n"
        f"Fault: {det['type']}. Readings: {json.dumps(event['readings'], default=str)}\n"
        f"Probable causes: {json.dumps(result['probable_causes'])}\n"
        f"Assigned team: {result['team']['name']}. Restoration P50 {result['restoration']['p50'][11:16]}, "
        f"P90 {result['restoration']['p90'][11:16]}.\n\n"
        'Return JSON: {"title": "<work order title, max 10 words>", "description": "<3-4 sentence technician brief>", '
        '"first_checks": ["<3 ordered first checks>"]}'
    )
    out, call = llm.complete_json(SYSTEM, prompt, purpose="Work order brief")
    top = result["probable_causes"][0]
    title = (out or {}).get("title") or f"{asset['name']}: {det['type'].split('(')[0].strip()} restoration"
    description = (out or {}).get("description") or (
        f"{asset['name']} reported {det['type'].lower()}. Most probable cause: {top['cause'].lower()} "
        f"({int(top['probability'] * 100)}%). Team to attend, isolate, diagnose and restore service; "
        f"report progress against the P50 restoration estimate.")
    first_checks = (out or {}).get("first_checks") or result["checklist"][:3]

    with store.lock:
        inc = store.incidents[incident_id]
        wo_id = inc.get("work_order_id")
        priority = "P1" if det["severity"] in ("CRITICAL", "HIGH") else "P2"
        revision = 1
        if wo_id and wo_id in store.work_orders:
            revision = store.work_orders[wo_id]["revision"] + 1
        else:
            wo_id = store.next_id("WO", 2041)
        wo = {
            "id": wo_id,
            "incident_id": incident_id,
            "asset_id": asset["id"],
            "asset_name": asset["name"],
            "asset_type": asset["type"],
            "location": result["asset"]["location"],
            "title": title,
            "description": description,
            "first_checks": first_checks,
            "priority": priority,
            "status": "DISPATCHED",
            "team": result["team"],
            "created_at": store.work_orders.get(wo_id, {}).get("created_at", iso(now())),
            "updated_at": iso(now()),
            "on_site_at": result["on_site_at"],
            "repair_window": {"start": result["work_start"], **result["restoration"]},
            "probable_causes": result["probable_causes"],
            "parts": result["parts"],
            "safety_notes": result["safety_notes"],
            "checklist": result["checklist"],
            "revision": revision,
        }
        store.work_orders[wo_id] = wo
        store.teams[result["team"]["id"]]["status"] = "DISPATCHED"
    bus.publish("work_order.updated", {"id": wo_id, "incident_id": incident_id, "revision": revision})

    infra = {**result, "work_order_id": wo_id, "work_order_title": title, "description": description}
    update_incident(incident_id, infra=infra, work_order_id=wo_id)
    return {"infra": {"restoration": result["restoration"], "work_order_id": wo_id}}, {
        "summary": (f"{wo_id} rev {revision} dispatched to {result['team']['name']}; restoration "
                    f"P50 {result['restoration']['p50'][11:16]} / P90 {result['restoration']['p90'][11:16]}"),
        "llm": [call],
        "output": {"work_order": wo_id, "top_cause": top["cause"], "probability": top["probability"],
                   "restoration": result["restoration"], "team": result["team"]["name"]},
    }
