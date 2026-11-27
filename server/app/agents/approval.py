"""Controller-in-the-loop approval gate using LangGraph interrupts."""
from __future__ import annotations

import copy
import time

from langgraph.graph import END
from langgraph.types import Command, interrupt

from app.agents.runtime import finish_execution, start_execution, update_incident
from app.core.events import bus
from app.core.utils import add_min, iso, now, parse_dt
from app.data.store import store
from app.domain.network import reserve_base

UPDATE_TYPES = {
    "restoration_delayed": {
        "label": "Restoration delayed",
        "detail": "Field report: restoration pushed back by 90 minutes.",
        "shift": 90, "goto": "reassess",
    },
    "early_restoration": {
        "label": "Early restoration",
        "detail": "Conditions improving faster than forecast: restoration brought forward by 45 minutes.",
        "shift": -45, "goto": "reassess",
    },
    "crew_shortage": {
        "label": "Reserve crew unavailable",
        "detail": "Reserve crew at the primary base has been called out to another event.",
        "goto": "replan",
    },
    "inventory_drop": {
        "label": "Seat inventory reduced",
        "detail": "A partner disruption absorbed half of the spare seats on alternate services.",
        "inventory_factor": 0.5, "goto": "replan",
    },
}


def apply_update(state: dict, update_type: str) -> tuple[dict, str]:
    spec = UPDATE_TYPES[update_type]
    detection = copy.deepcopy(state["detection"])
    adjustments = copy.deepcopy(state.get("adjustments", {}))
    scope = detection["scope"]
    if "shift" in spec:
        scope["end"] = iso(add_min(parse_dt(scope["end"]), spec["shift"]))
        if scope["type"] != "AIRPORT_CLOSURE":
            adjustments["window_shift_min"] = adjustments.get("window_shift_min", 0) + spec["shift"]
    if update_type == "crew_shortage":
        node = scope.get("node")
        adjustments["reserve_unavailable"] = sorted(set(adjustments.get("reserve_unavailable", [])) | {reserve_base(node)})
    if "inventory_factor" in spec:
        adjustments["inventory_factor"] = spec["inventory_factor"]
    return {"detection": detection, "adjustments": adjustments}, spec["goto"]


def approval_node(state: dict) -> Command:
    incident_id = state["incident_id"]
    version = state.get("plan_version", 1)
    with store.lock:
        trace = store.incidents[incident_id]["trace"]
        ex = next((e for e in reversed(trace) if e["node"] == "controller_approval"
                   and e["status"] == "waiting" and e["plan_version"] == version), None)
    if ex is None:
        ex = start_execution(incident_id, "controller_approval", version)
        with store.lock:
            ex["status"] = "waiting"
            ex["summary"] = "Waiting for duty controller decision"
        update_incident(incident_id, status="AWAITING_APPROVAL")
        bus.publish("approval.required", {"incident_id": incident_id, "plan_version": version,
                                          "recommended": state["recommendation"]["option_id"]})
    started = time.perf_counter() - max(0.0, (now() - parse_dt(ex["started_at"])).total_seconds())

    decision = interrupt({
        "incident_id": incident_id,
        "plan_version": version,
        "options": [o["id"] for o in state["options"]],
        "recommended": state["recommendation"]["option_id"],
    })

    action = decision.get("action")
    controller = decision.get("controller", "Duty controller")
    record = {**decision, "decided_at": iso(now()), "plan_version": version}

    if action == "approve":
        option_id = decision["option_id"]
        option = next(o for o in state["options"] if o["id"] == option_id)
        record["override"] = option_id != state["recommendation"]["option_id"]
        record["option_name"] = option["name"]
        summary = f"{controller} approved {option['letter']} - {option['name']}" + (" (override)" if record["override"] else "")
        finish_execution(incident_id, ex, "completed", summary, output=record, started=started)
        update_incident(incident_id, decision=record, status="EXECUTING")
        return Command(goto="traveler_notification", update={"decision": record})

    if action == "reject":
        finish_execution(incident_id, ex, "completed", f"{controller} rejected all options; manual handling", output=record, started=started)
        update_incident(incident_id, decision=record, status="REJECTED")
        return Command(goto=END, update={"decision": record})

    if action == "replan":
        prefs = {**state.get("preferences", {}), **(decision.get("preferences") or {})}
        reason = f"Controller re-plan: priority {prefs.get('priority', 'balanced')}"
        if prefs.get("max_delay_min"):
            reason += f", max delay {prefs['max_delay_min']} min"
        if prefs.get("avoid_cancellations"):
            reason += ", avoid cancellations"
        finish_execution(incident_id, ex, "completed", reason, output=record, started=started)
        with store.lock:
            store.incidents[incident_id]["_replan_reason"] = reason
        update_incident(incident_id, status="REPLANNING", preferences=prefs)
        return Command(goto="recovery_planner", update={"preferences": prefs, "plan_version": version + 1, "decision": record})

    if action == "update":
        update_type = decision["update_type"]
        changes, goto = apply_update(state, update_type)
        spec = UPDATE_TYPES[update_type]
        entry = {"type": update_type, "label": spec["label"], "detail": spec["detail"], "at": iso(now()), "plan_version": version}
        finish_execution(incident_id, ex, "completed", f"New information: {spec['label']}", output=entry, started=started)
        with store.lock:
            inc = store.incidents[incident_id]
            inc.setdefault("updates", []).append(entry)
            inc["_replan_reason"] = f"{spec['label']}: {spec['detail']}"
        update_incident(incident_id, status="REPLANNING", detection=changes["detection"])
        bus.publish("feed.update", {"incident_id": incident_id, **entry})
        targets = ["impact_analysis", "infra_triage"] if goto == "reassess" else "recovery_planner"
        return Command(goto=targets, update={**changes, "plan_version": version + 1})

    raise ValueError(f"Unsupported controller action: {action}")
