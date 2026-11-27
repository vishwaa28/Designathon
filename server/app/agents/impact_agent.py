from __future__ import annotations

import json
from collections import Counter

from app.agents.runtime import agent_node, update_incident
from app.core.llm import llm
from app.core.utils import add_min, minutes_between
from app.data import reference as ref
from app.data.store import is_priority, store
from app.domain import contacts, network
from app.domain.recovery import COST

SYSTEM = ("You are the network impact analyst in an operations control centre. Explain cascading effects "
          "of a disruption across aircraft/rake rotations, crew duty limits and passenger connections in plain operational language.")


def _delay_band(d: int) -> str:
    if d < 60:
        return "15-59 min"
    if d < 120:
        return "1-2 h"
    if d < 240:
        return "2-4 h"
    return "4 h+"


@agent_node("impact_analysis")
def impact_node(state: dict) -> tuple[dict, dict]:
    det = state["detection"]
    scope = det["scope"]
    with store.lock:
        contact_pax = contacts.attach(scope)
        primary = network.primary_delays(scope)
        delays = network.propagate(primary)
        breaches = network.crew_breaches(delays)
        effects = network.pax_effects(delays)

        missed_by_trip: Counter = Counter()
        priority_by_trip: Counter = Counter()
        pax_by_trip_affected: Counter = Counter()
        for pid, e in effects.items():
            p = store.passengers[pid]
            if e["missed"]:
                missed_by_trip[e["missed"][0]] += 1
            for tid in p["legs"]:
                if tid in delays:
                    pax_by_trip_affected[tid] += 1
                    if is_priority(p):
                        priority_by_trip[tid] += 1
        breach_trips = {tid for b in breaches for tid in store.pairings[b["pairing_id"]]["trip_ids"]}

        trips = []
        for tid, d in sorted(delays.items(), key=lambda x: store.trips[x[0]]["sched_dep"]):
            if d < 15:
                continue
            t = store.trips[tid]
            view = store.trip_view(t)
            view.update({
                "projected_delay_min": d,
                "projected_dep": add_min(t["sched_dep"], d).isoformat(),
                "impact_type": "DIRECT" if tid in primary else "CASCADE",
                "pax_affected": pax_by_trip_affected.get(tid, store.booked(tid)),
                "connections_at_risk": missed_by_trip.get(tid, 0),
                "priority_pax": priority_by_trip.get(tid, 0),
                "crew_breach": tid in breach_trips,
            })
            trips.append(view)

        missed = []
        priority = []
        tiers: Counter = Counter()
        ssrs: Counter = Counter()
        bands: Counter = Counter()
        for pid, e in effects.items():
            p = store.passengers[pid]
            if p["tier"]:
                tiers[p["tier"]] += 1
            if p["ssr"]:
                ssrs[p["ssr"]] += 1
            if e["delay"]:
                bands[_delay_band(e["delay"])] += 1
            if e["missed"]:
                a, b = (store.trips[x] for x in e["missed"])
                avail = minutes_between(add_min(a["sched_arr"], delays.get(a["id"], 0)),
                                        add_min(b["sched_dep"], delays.get(b["id"], 0)))
                missed.append({"pax_id": pid, "pnr": p["pnr"], "name": f"{p['first_name']} {p['last_name']}",
                               "tier": p["tier"], "ssr": p["ssr"], "from_trip": a["number"], "to_trip": b["number"],
                               "connection_at": ref.city_of(a["destination"]),
                               "available_min": avail, "required_min": network.min_connection(a, b)})
            if is_priority(p):
                leg = store.trips[e["delay_leg"] or e["cancelled_leg"] or p["legs"][0]]
                priority.append({"pax_id": pid, "pnr": p["pnr"], "name": f"{p['first_name']} {p['last_name']}",
                                 "tier": p["tier"], "ssr": p["ssr"], "trip": leg["number"], "delay_min": e["delay"],
                                 "missed_connection": bool(e["missed"])})
        priority.sort(key=lambda x: (x["ssr"] is None, -(x["delay_min"] or 0)))

        baseline = sum(d * COST["delay_per_min"][store.trips[t]["mode"]] for t, d in delays.items())
        baseline += sum(COST["care_2h"]["FLIGHT"] for e in effects.values() if e["delay"] >= 120)
        baseline += len(missed) * (COST["hotel"]["FLIGHT"] + COST["rebook"]["FLIGHT"])

    summary = {
        "trips_direct": sum(1 for t in trips if t["impact_type"] == "DIRECT"),
        "trips_cascade": sum(1 for t in trips if t["impact_type"] == "CASCADE"),
        "flights": sum(1 for t in trips if t["mode"] == "FLIGHT"),
        "trains": sum(1 for t in trips if t["mode"] == "TRAIN"),
        "pax_affected": len(effects),
        "missed_connections": len(missed),
        "crew_pairings_breached": len(breaches),
        "crew_members_breached": sum(len(b["members"]) for b in breaches),
        "priority_pax": len(priority),
        "max_delay_min": max((t["projected_delay_min"] for t in trips), default=0),
        "tiers": dict(tiers),
        "ssr": dict(ssrs),
        "delay_bands": dict(bands),
        "baseline_cost": int(baseline),
    }
    prompt = (
        f"Disruption: {det['type']} at {det.get('location_label')} ({det['severity']}).\n"
        f"Impact totals: {json.dumps(summary)}\n"
        f"Most delayed services: {json.dumps([{k: t[k] for k in ('number', 'origin', 'destination', 'projected_delay_min', 'impact_type', 'pax_affected')} for t in sorted(trips, key=lambda x: -x['projected_delay_min'])[:8]])}\n"
        f"Crew breaches: {json.dumps([{k: b[k] for k in ('swap_trip', 'projected_duty_h', 'reserve_base')} for b in breaches[:5]], default=str)}\n\n"
        'Return JSON: {"narrative": "<3 sentences on how the disruption cascades>", "key_risks": ["<3 short risks>"]}'
    )
    out, call = llm.complete_json(SYSTEM, prompt, purpose="Cascade narrative")
    narrative = (out or {}).get("narrative") or (
        f"{summary['trips_direct']} services are hit directly and {summary['trips_cascade']} more inherit delay through "
        f"vehicle rotations. {summary['pax_affected']} passengers are affected, {summary['missed_connections']} of them "
        f"at risk of missing connections, and {summary['crew_pairings_breached']} crew pairings would exceed duty limits.")
    impact = {
        "summary": summary,
        "trips": trips,
        "crew_breaches": breaches,
        "missed_connections": missed[:80],
        "priority_passengers": priority[:80],
        "contact_passengers": contact_pax,
        "narrative": narrative,
        "key_risks": (out or {}).get("key_risks") or [
            "Crew duty-time limits on late rotations", "Connection banks at the hub", "Seat inventory for re-accommodation"],
    }
    update_incident(state["incident_id"], impact=impact)
    return {"impact": {"summary": summary}}, {
        "summary": (f"{len(trips)} services affected ({summary['trips_cascade']} by cascade), {summary['pax_affected']} passengers, "
                    f"{summary['missed_connections']} missed connections, {summary['crew_pairings_breached']} crew breaches"),
        "llm": [call],
        "output": summary,
    }
