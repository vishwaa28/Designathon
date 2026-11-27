"""Runs and resumes LangGraph executions on worker threads."""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from langgraph.types import Command

from app.agents.graph import recovery_graph
from app.agents.runtime import update_incident
from app.core.events import bus
from app.core.utils import iso, now
from app.data import reference as ref
from app.data.store import store
from app.services import feeds

log = logging.getLogger("arro.orchestrator")
executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="graph")

# Serverless hosts (Vercel) only keep the instance alive for tracked work, so the API passes
# FastAPI's BackgroundTasks.add_task; scripts and tests fall back to the thread pool.
Schedule = Callable[..., object]


class WorkflowError(Exception):
    pass


def _config(incident_id: str) -> dict:
    return {"configurable": {"thread_id": incident_id}}


def _invoke(incident_id: str, payload) -> None:
    try:
        recovery_graph.invoke(payload, _config(incident_id))
    except Exception as exc:  # noqa: BLE001
        log.exception("Workflow failed for %s", incident_id)
        update_incident(incident_id, status="FAILED", error=f"{type(exc).__name__}: {exc}")


def trigger_scenario(scenario_id: str, schedule: Schedule | None = None) -> dict:
    event = feeds.build_event(scenario_id)
    created = iso(now())
    with store.lock:
        incident_id = store.next_id("INC", 1001)
        incident = {
            "id": incident_id, "title": event["title"], "scenario_id": scenario_id,
            "category": event["category"], "mode": event["mode"], "severity": "PENDING", "status": "DETECTING",
            "created_at": created, "updated_at": created, "resolved_at": None,
            "location": ref.display_code(event["location"]), "event": event,
            "detection": None, "impact": None, "infra": None, "options": [], "recommendation": None,
            "decision": None, "notifications": None, "plan_version": 1, "plan_history": [], "updates": [],
            "trace": [], "work_order_id": None, "preferences": {"priority": "balanced"}, "error": None,
        }
        store.incidents[incident_id] = incident
    level = "critical"
    feeds.publish_feed("WEATHER" if event["category"] == "WEATHER" else "ASSET", level, event["title"],
                       event["description"], incident_id)
    bus.publish("incident.created", {"id": incident_id, "title": event["title"]})
    initial = {"incident_id": incident_id, "event": event, "plan_version": 1,
               "preferences": {"priority": "balanced"}, "adjustments": {}, "history": []}
    (schedule or executor.submit)(_invoke, incident_id, initial)
    return incident


def _wait_for_interrupt(incident_id: str, timeout_s: float = 5.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        snapshot = recovery_graph.get_state(_config(incident_id))
        if snapshot.next == ("controller_approval",) and snapshot.interrupts:
            return
        time.sleep(0.1)
    raise WorkflowError("Workflow is not waiting for a decision")


def _resume(incident_id: str, decision: dict, schedule: Schedule | None = None) -> None:
    with store.lock:
        inc = store.incidents.get(incident_id)
        if inc is None:
            raise KeyError(incident_id)
        if inc["status"] != "AWAITING_APPROVAL":
            raise WorkflowError(f"Incident is {inc['status']}, not awaiting approval")
        inc["status"] = "PROCESSING"
    try:
        _wait_for_interrupt(incident_id)
    except WorkflowError:
        update_incident(incident_id, status="AWAITING_APPROVAL")
        raise
    bus.publish("incident.updated", {"id": incident_id, "status": "PROCESSING", "fields": ["status"]})
    (schedule or executor.submit)(_invoke, incident_id, Command(resume=decision))


def submit_decision(incident_id: str, decision: dict, schedule: Schedule | None = None) -> None:
    inc = store.incidents.get(incident_id)
    if inc is None:
        raise KeyError(incident_id)
    if decision["action"] == "approve":
        if not any(o["id"] == decision.get("option_id") for o in inc["options"]):
            raise WorkflowError("Unknown option for the current plan version")
    _resume(incident_id, decision, schedule)


def push_update(incident_id: str, update_type: str, controller: str, schedule: Schedule | None = None) -> None:
    _resume(incident_id, {"action": "update", "update_type": update_type, "controller": controller}, schedule)
