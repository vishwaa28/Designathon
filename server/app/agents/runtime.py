"""Execution tracing for graph nodes: timing, model calls and live event publishing."""
from __future__ import annotations

import functools
import time
from typing import Any, Callable

from app.config import settings
from app.core.events import bus
from app.core.utils import iso, now
from app.data.store import store


def update_incident(incident_id: str, **fields: Any) -> dict:
    with store.lock:
        inc = store.incidents[incident_id]
        inc.update(fields)
        inc["updated_at"] = iso(now())
    bus.publish("incident.updated", {"id": incident_id, "status": inc["status"], "fields": list(fields)})
    return inc


def start_execution(incident_id: str, node: str, plan_version: int) -> dict:
    ex = {
        "id": store.next_id("EX", 1),
        "node": node,
        "status": "running",
        "started_at": iso(now()),
        "ended_at": None,
        "duration_ms": None,
        "summary": "",
        "llm": [],
        "output": {},
        "plan_version": plan_version,
    }
    with store.lock:
        store.incidents[incident_id]["trace"].append(ex)
    bus.publish("agent.started", {"incident_id": incident_id, "node": node, "execution_id": ex["id"]})
    return ex


def finish_execution(incident_id: str, ex: dict, status: str, summary: str = "",
                     llm_calls: list | None = None, output: dict | None = None, started: float | None = None) -> None:
    with store.lock:
        ex["status"] = status
        ex["ended_at"] = iso(now())
        if started is not None:
            ex["duration_ms"] = int((time.perf_counter() - started) * 1000)
        ex["summary"] = summary
        ex["llm"] = [c.to_dict() if hasattr(c, "to_dict") else c for c in (llm_calls or [])]
        ex["output"] = output or {}
    bus.publish(f"agent.{status}", {"incident_id": incident_id, "node": ex["node"], "execution_id": ex["id"],
                                    "summary": summary, "duration_ms": ex["duration_ms"]})


def agent_node(name: str) -> Callable:
    """Wrap a node function returning (state_update, info) with tracing.

    ``info`` keys: summary (str), llm (list[LLMCall]), output (dict shown in the inspector).
    """

    def decorator(fn: Callable[[dict], tuple[dict, dict]]) -> Callable[[dict], dict]:
        @functools.wraps(fn)
        def wrapper(state: dict) -> dict:
            incident_id = state["incident_id"]
            ex = start_execution(incident_id, name, state.get("plan_version", 1))
            started = time.perf_counter()
            try:
                update, info = fn(state)
            except Exception as exc:
                finish_execution(incident_id, ex, "failed", f"{type(exc).__name__}: {exc}", started=started)
                raise
            remaining = settings.agent_step_delay_s - (time.perf_counter() - started)
            if remaining > 0:
                time.sleep(remaining)
            finish_execution(incident_id, ex, "completed", info.get("summary", ""), info.get("llm"),
                             info.get("output"), started)
            return update

        return wrapper

    return decorator
