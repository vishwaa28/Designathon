from __future__ import annotations

import json

from app.agents.runtime import agent_node, update_incident
from app.core.llm import llm
from app.core.utils import iso, now
from app.domain import detection

SYSTEM = ("You are the disruption detection specialist in a combined airline, airport and rail operations "
          "control centre. Write crisp, factual situation reports for duty controllers. No speculation beyond the data.")


@agent_node("detection")
def detection_node(state: dict) -> tuple[dict, dict]:
    event = state["event"]
    result = detection.assess(event)
    brief = {k: event[k] for k in ("title", "source", "category", "kind", "readings") if k in event}
    prompt = (
        f"Feed event:\n{json.dumps(brief, default=str)}\n\n"
        f"Threshold evaluation:\n{json.dumps(result['triggers'], default=str)}\n"
        f"Rule-based severity: {result['severity']}. Disruption type: {result['type']}. "
        f"Location: {result.get('location_label')}. Initial window: {result.get('initial_window')}.\n\n"
        'Return JSON: {"headline": "<max 12 words>", "summary": "<2-3 sentence situation report>", '
        '"watch_items": ["<3 short items controllers should monitor>"]}'
    )
    out, call = llm.complete_json(SYSTEM, prompt, purpose="Situation report")
    breached = [t for t in result["triggers"] if t["breached"]]
    fallback_summary = (
        f"{result['type']} detected at {result.get('location_label')}. "
        + "; ".join(f"{t['signal']} {t['value']}{(' ' + t['unit']) if t['unit'] else ''} (limit {t['threshold']})" for t in breached)
        + f". Initial disruption window estimated until {result['initial_window']['end'][11:16]}."
    )
    det = {
        **result,
        "headline": (out or {}).get("headline") or event["title"],
        "summary": (out or {}).get("summary") or fallback_summary,
        "watch_items": (out or {}).get("watch_items") or [
            "Feed updates on restoration estimate", "Crew duty-time exposure", "Connection banks at the hub"],
        "detected_at": iso(now()),
        "narrative_source": call.provider if out else "rules",
    }
    status = "ANALYZING" if det["is_disruption"] else "NO_ACTION"
    update_incident(state["incident_id"], detection=det, severity=det["severity"], status=status,
                    location=det.get("location_label"))
    summary = (f"{det['severity']} {det['type'].lower()} at {det.get('location_label')}; "
               f"{det['breached']}/{len(det['triggers'])} thresholds breached, confidence {int(det['confidence'] * 100)}%")
    return {"detection": det}, {
        "summary": summary, "llm": [call],
        "output": {"severity": det["severity"], "type": det["type"], "confidence": det["confidence"],
                   "scope": det["scope"], "breached_signals": [t["signal"] for t in breached]},
    }


def route_after_detection(state: dict) -> list[str] | str:
    if state.get("detection", {}).get("is_disruption"):
        return ["impact_analysis", "infra_triage"]
    return "__end__"
