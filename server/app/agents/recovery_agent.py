from __future__ import annotations

from app.agents.runtime import agent_node, update_incident
from app.data.store import store
from app.domain import recovery


@agent_node("recovery_planner")
def recovery_node(state: dict) -> tuple[dict, dict]:
    det = state["detection"]
    infra = state["infra"]
    version = state.get("plan_version", 1)
    ctx = {
        "scope": det["scope"],
        "restoration": infra["restoration"],
        "adjustments": state.get("adjustments", {}),
        "preferences": state.get("preferences", {}),
        "plan_version": version,
    }
    with store.lock:
        options, artifacts = recovery.generate_options(ctx)
        store.plan_artifacts.update(artifacts)
    update_incident(state["incident_id"], status="PLANNING", plan_version=version)
    return {"options": options}, {
        "summary": "; ".join(
            f"{o['letter']}: {o['name']} ({o['metrics']['trips_delayed']} delayed, {o['metrics']['trips_cancelled']} cancelled)"
            for o in options),
        "output": {"plan_version": version, "restoration_p50": infra["restoration"]["p50"],
                   "options": [{"id": o["id"], "name": o["name"], "cost": o["cost"]["total"],
                                "pax_affected": o["metrics"]["pax_affected"]} for o in options]},
    }
