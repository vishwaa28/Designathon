from __future__ import annotations

import copy
import json

from app.agents.runtime import agent_node, update_incident
from app.core.llm import llm
from app.core.utils import iso, now
from app.data.store import store
from app.domain import scoring

SYSTEM = ("You are the decision-support analyst for a duty operations controller. Explain the trade-offs "
          "between recovery options honestly and specifically, quoting the numbers provided. Never invent figures.")


def _brief(o: dict) -> dict:
    m = o["metrics"]
    return {
        "id": o["id"], "name": o["name"], "summary": o["summary"], "score": o["score"], "confidence": o["confidence"],
        "cost_inr": o["cost"]["total"], "trips_delayed": m["trips_delayed"], "trips_cancelled": m["trips_cancelled"],
        "avg_delay_min": m["avg_delay_min"], "max_delay_min": m["max_delay_min"], "pax_affected": m["pax_affected"],
        "pax_rebooked": m["pax_rebooked"], "pax_alt_mode": m["pax_alt_mode"], "pax_unaccommodated": m["pax_unaccommodated"],
        "connections_protected": f"{m['connections_protected']}/{m['connections_missed']}",
        "crew_breaches_unresolved": m["crew_unresolved"], "recovery_min": m["recovery_min"],
        "repair_dependent": o["repair_dependent"], "p90_sensitivity": o.get("sensitivity"),
        "constraints": [f"{c['name']}: {c['status']}" for c in o["constraints"] if c["status"] != "PASS"],
    }


@agent_node("tradeoff_analyst")
def tradeoff_node(state: dict) -> tuple[dict, dict]:
    options = copy.deepcopy(state["options"])
    preferences = state.get("preferences", {})
    restoration = state["infra"]["restoration"]
    rec = scoring.score_options(options, restoration, preferences)
    facts = scoring.rule_tradeoffs(options)

    prompt = (
        f"Disruption: {state['detection']['type']} at {state['detection'].get('location_label')}.\n"
        f"Controller priority: {rec['priority']} (weights {json.dumps(rec['weights'])}).\n"
        f"Options:\n{json.dumps([_brief(o) for o in options], default=str)}\n"
        f"Recommended by scoring: {rec['option_id']}.\n\n"
        'Return JSON: {"options": {"<option id>": {"explanation": "<2 sentences on the trade-off>", '
        '"pros": ["<max 3>"], "cons": ["<max 3>"]}}, "rationale": "<2-3 sentences on why the recommended option wins and what would change the decision>"}'
    )
    out, call = llm.complete_json(SYSTEM, prompt, purpose="Trade-off explanation")
    model_opts = (out or {}).get("options") or {}
    for o in options:
        m = model_opts.get(o["id"]) or {}
        f = facts[o["id"]]
        o["explanation"] = m.get("explanation") or f["explanation"]
        o["pros"] = (m.get("pros") or f["pros"])[:4]
        o["cons"] = (m.get("cons") or f["cons"])[:4]

    best = next(o for o in options if o["recommended"])
    rationale = (out or {}).get("rationale") or (
        f"{best['name']} scores highest ({best['score']}/100) under the {rec['priority']} weighting with "
        f"{int(best['confidence'] * 100)}% confidence. "
        + ("It does not depend on the repair window holding. " if not best["repair_dependent"] else
           "Its outcome depends on the repair window; if restoration slips towards P90 the alternatives become more attractive. "))
    recommendation = {**rec, "rationale": rationale, "generated_at": iso(now()),
                      "narrative_source": call.provider if out else "rules"}

    version = state.get("plan_version", 1)
    with store.lock:
        inc = store.incidents[state["incident_id"]]
        history = inc.setdefault("plan_history", [])
        history.append({
            "version": version, "at": iso(now()), "reason": inc.get("_replan_reason", "Initial plan"),
            "recommended": best["id"], "recommended_name": best["name"], "score": best["score"],
            "priority": rec["priority"], "cost": best["cost"]["total"],
        })
    update_incident(state["incident_id"], options=options, recommendation=recommendation)
    return {"options": options, "recommendation": recommendation,
            "history": [{"version": version, "recommended": best["id"]}]}, {
        "summary": f"Recommends {best['letter']} - {best['name']} (score {best['score']}, confidence {int(best['confidence'] * 100)}%)",
        "llm": [call],
        "output": {"ranking": [{"id": o["id"], "score": o["score"], "confidence": o["confidence"]}
                               for o in sorted(options, key=lambda x: -x["score"])],
                   "weights": rec["weights"]},
    }
