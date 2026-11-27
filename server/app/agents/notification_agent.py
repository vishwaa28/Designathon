from __future__ import annotations

import json
from collections import Counter

from app.agents.runtime import agent_node, update_incident
from app.core.events import bus
from app.core.llm import llm
from app.core.utils import iso, now
from app.data import reference as ref
from app.data.store import is_priority, store
from app.domain import contacts
from app.domain import notifications as nt
from app.services import delivery

SYSTEM = ("You write proactive traveler notifications for an airline. Messages are short "
          "(under 320 characters), empathetic, specific and actionable. You are fluent in Indian languages.")

OUTCOME_STATUS = {
    "DELAYED": "DELAYED", "REBOOKED": "REBOOKED",
    "DIVERTED": "DIVERTED", "UNACCOMMODATED": "REFUND_OFFERED",
}


def _execute_plan(incident_id: str, artifacts: dict) -> dict:
    """Write the approved plan into the operational schedule and bookings."""
    changed = Counter()
    for tid, d in artifacts["delays"].items():
        t = store.trips[tid]
        if d != t["delay_min"]:
            t["delay_min"] = d
            changed["retimed"] += 1
        if incident_id not in t["disruption_ids"]:
            t["disruption_ids"].append(incident_id)
    for tid in artifacts["cancels"]:
        t = store.trips[tid]
        t["cancelled"] = True
        t["remarks"] = "Cancelled under recovery plan"
        if incident_id not in t["disruption_ids"]:
            t["disruption_ids"].append(incident_id)
        changed["cancelled"] += 1
    for tid, alt in artifacts["diversions"].items():
        store.trips[tid]["diverted_to"] = alt
        store.trips[tid]["remarks"] = f"Diverted to {ref.display_code(alt)}"
        changed["diverted"] += 1
    for pid, o in artifacts["pax_outcomes"].items():
        p = store.passengers[pid]
        if o.get("new_trip") and o["leg"] in p["legs"]:
            p["legs"] = [o["new_trip"] if leg == o["leg"] else leg for leg in p["legs"]]
            store.pax_by_trip[o["leg"]].discard(pid)
            store.pax_by_trip[o["new_trip"]].add(pid)
            changed["pax_moved"] += 1
        p["status"] = OUTCOME_STATUS[o["type"]]
    return dict(changed)


@agent_node("traveler_notification")
def notification_node(state: dict) -> tuple[dict, dict]:
    incident_id = state["incident_id"]
    decision = state["decision"]
    option = next(o for o in state["options"] if o["id"] == decision["option_id"])
    det = state["detection"]
    loc = det.get("location_label", "")

    with store.lock:
        artifacts = store.plan_artifacts[option["id"]]
        changes = _execute_plan(incident_id, artifacts)
        outcomes = artifacts["pax_outcomes"]
        lang_counts = Counter(store.passengers[pid]["language"] for pid in outcomes)
    outcome_types = sorted({o["type"] for o in outcomes.values()})
    languages = ["en"] + [l for l, _ in lang_counts.most_common() if l != "en"][:4]
    scope_type = det["scope"]["type"]
    reasons = {lang: table[scope_type].format(loc=loc) for lang, table in nt.REASONS.items()}
    reason_en = reasons["en"]

    prompt = (
        f"Disruption reason (English): {reason_en}.\n"
        f"Approved plan: {option['name']} - {option['summary']}\n"
        f"Outcome types needing a template: {outcome_types} (DELAYED=same trip later, REBOOKED=moved to another flight, "
        f"DIVERTED=landing at alternate with coach, "
        f"UNACCOMMODATED=no seat, refund or next-day).\n"
        f"Languages: {[ref.LANGUAGES[l] + ' (' + l + ')' for l in languages]}.\n"
        f"Use these exact placeholders where relevant: {nt.PLACEHOLDERS} ({nt.PLACEHOLDER_NOTES}). Always include {{link}} in outcome templates. "
        f"Write the reason directly in each language (no {{reason}} placeholder). Also add a key PRIORITY with a one-line "
        f"note, without any placeholders, that a priority assistance agent will call (it is appended to the message).\n\n"
        'Return JSON: {"templates": {"<lang code>": {"<OUTCOME_TYPE>": "<template>", "PRIORITY": "<line>"}}}'
    )
    out, call = llm.complete_json(SYSTEM, prompt, purpose="Multilingual notifications")
    model_templates = (out or {}).get("templates") or {}

    def templates_for(lang: str) -> tuple[dict, str]:
        t = model_templates.get(lang)
        if isinstance(t, dict) and all(isinstance(t.get(k), str) and "{link}" in t[k] for k in outcome_types):
            return t, lang
        if lang in nt.FALLBACK_TEMPLATES:
            return nt.FALLBACK_TEMPLATES[lang], lang
        t = model_templates.get("en")
        if isinstance(t, dict) and all(isinstance(t.get(k), str) and "{link}" in t[k] for k in outcome_types):
            return t, "en"
        return nt.FALLBACK_TEMPLATES["en"], "en"

    sent_at = iso(now())
    records = []
    outbound = []
    with store.lock:
        for pid, o in outcomes.items():
            p = store.passengers[pid]
            templates, used_lang = templates_for(p["language"])
            body = (nt.render(templates[o["type"]], p, o, reasons.get(used_lang, reason_en), used_lang)
                    + nt.priority_line(p, templates))
            if p.get("contact"):
                english = None
                if used_lang != "en":
                    en_templates, _ = templates_for("en")
                    english = nt.render(en_templates[o["type"]], p, o, reason_en, "en")
                outbound.append((len(records), dict(p), english))
            records.append({
                "id": store.next_id("NTF", 100001),
                "incident_id": incident_id,
                "pax_id": pid,
                "pnr": p["pnr"],
                "name": f"{p['first_name']} {p['last_name']}",
                "last_name": p["last_name"],
                "language": used_lang,
                "language_label": ref.LANGUAGES.get(used_lang, used_lang),
                "channel": p["channel"],
                "outcome": o["type"],
                "subject": nt.SUBJECTS[o["type"]],
                "message": body,
                "priority": is_priority(p),
                "escalation": "AGENT_CALL" if nt.needs_agent_call(p) else None,
                "trip": store.trips[o["leg"]]["number"] if o.get("leg") else None,
                "new_trip": store.trips[o["new_trip"]]["number"] if o.get("new_trip") else None,
                "status": "DELIVERED",
                "sent_at": sent_at,
                "self_service_url": nt.portal_link(p["pnr"], p["last_name"]),
                "contact": bool(p.get("contact")),
            })
        # A contact traveler holds a booking on every flight: send the real e-mail/SMS for their soonest affected flight only.
        keep = set(contacts.earliest_per_contact([pax["id"] for _, pax, _ in outbound]))
        outbound = [o for o in outbound if o[1]["id"] in keep]
        for rec in records:
            if rec["contact"] and rec["pax_id"] not in keep:
                rec["deliveries"] = []
        store.notifications.extend(records)

    delivery_counts = delivery.deliver_many([(records[i], pax, english) for i, pax, english in outbound])

    summary = {
        "total": len(records),
        "by_outcome": dict(Counter(r["outcome"] for r in records)),
        "by_channel": dict(Counter(r["channel"] for r in records)),
        "by_language": dict(Counter(r["language_label"] for r in records)),
        "priority": sum(1 for r in records if r["priority"]),
        "agent_calls": sum(1 for r in records if r["escalation"]),
        "sent_at": sent_at,
        "plan_changes": changes,
        "delivery": delivery_counts,
        "template_source": call.provider if model_templates else "built-in templates",
    }
    update_incident(incident_id, notifications=summary, status="RESOLVED", resolved_at=sent_at)
    bus.publish("notifications.sent", {"incident_id": incident_id, "total": len(records)})
    return {"notifications": summary}, {
        "summary": (f"{len(records)} travelers notified in {len(summary['by_language'])} languages; "
                    f"{delivery_counts['email_sent']} e-mails and {delivery_counts['sms_sent']} SMS sent; "
                    f"{summary['agent_calls']} assisted calls queued; schedule updated"),
        "llm": [call],
        "output": summary,
    }
