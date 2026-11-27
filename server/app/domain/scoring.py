"""Multi-criteria scoring, confidence estimation and rule-based trade-off narratives."""
from __future__ import annotations

from datetime import datetime

from app.core.utils import clamp, now, parse_dt

WEIGHTS = {
    "balanced": {"passenger": 0.35, "cost": 0.25, "risk": 0.20, "time": 0.20},
    "passenger": {"passenger": 0.55, "cost": 0.15, "risk": 0.15, "time": 0.15},
    "cost": {"passenger": 0.20, "cost": 0.50, "risk": 0.15, "time": 0.15},
    "speed": {"passenger": 0.20, "cost": 0.15, "risk": 0.15, "time": 0.50},
}
CRITERIA_LABELS = {"passenger": "Passenger impact", "cost": "Cost", "risk": "Operational risk", "time": "Recovery time"}


def passenger_index(m: dict) -> float:
    return (m["pax_delay_hours"] + 1.0 * m["pax_rebooked"]
            + 6.0 * m["pax_unaccommodated"] + 2.0 * (m["connections_missed"] - m["connections_protected"])
            + 3.0 * m["priority_unprotected"])


def risk_index(option: dict, uncertainty_h: float) -> float:
    fails = sum(1 for c in option["constraints"] if c["status"] == "FAIL")
    warns = sum(1 for c in option["constraints"] if c["status"] == "WARN")
    dependency = uncertainty_h * 2.0 if option["repair_dependent"] else 0.0
    return option["metrics"]["crew_unresolved"] * 3.0 + fails * 4.0 + warns * 1.0 + dependency + 0.5


def _normalise(values: list[float]) -> list[float]:
    lo, hi = min(values), max(values)
    if hi - lo < 1e-9:
        return [0.0 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]


def score_options(options: list[dict], restoration: dict, preferences: dict, data_quality: float = 0.92) -> dict:
    priority = preferences.get("priority", "balanced")
    weights = WEIGHTS.get(priority, WEIGHTS["balanced"])
    p50, p90 = parse_dt(restoration["p50"]), parse_dt(restoration["p90"])
    ref_time = now()
    uncertainty_h = max(0.0, (p90 - p50).total_seconds() / 3600)
    horizon_h = max(0.5, (p50 - ref_time).total_seconds() / 3600)

    raw = {
        "passenger": [passenger_index(o["metrics"]) for o in options],
        "cost": [float(o["cost"]["total"]) for o in options],
        "risk": [risk_index(o, uncertainty_h) for o in options],
        "time": [float(o["metrics"]["recovery_min"]) for o in options],
    }
    norm = {k: _normalise(v) for k, v in raw.items()}

    for i, o in enumerate(options):
        breakdown = {k: round(100 * (1 - norm[k][i])) for k in weights}
        weighted = sum(weights[k] * norm[k][i] for k in weights)
        fails = sum(1 for c in o["constraints"] if c["status"] == "FAIL")
        warns = sum(1 for c in o["constraints"] if c["status"] == "WARN")
        score = 100 - 45 * weighted - 12 * fails - 3 * warns
        conf = data_quality
        if o["repair_dependent"]:
            conf -= min(0.25, 0.25 * uncertainty_h / horizon_h)
        conf -= 0.04 * warns + 0.12 * fails
        need = o["metrics"]["pax_rebooked"] + o["metrics"]["pax_unaccommodated"]
        if need and o["metrics"]["pax_unaccommodated"] / need > 0.05:
            conf -= 0.06
        o["score"] = int(round(clamp(score, 5, 99)))
        o["confidence"] = round(clamp(conf, 0.35, 0.97), 2)
        o["criteria"] = breakdown
        o["raw_criteria"] = {k: round(raw[k][i], 1) for k in raw}

    feasible = [o for o in options if not any(c["status"] == "FAIL" for c in o["constraints"])] or options
    best = max(feasible, key=lambda o: (o["score"], o["confidence"]))
    for o in options:
        o["recommended"] = o["id"] == best["id"]
    return {"option_id": best["id"], "weights": weights, "priority": priority,
            "criteria_labels": CRITERIA_LABELS, "uncertainty_h": round(uncertainty_h, 2)}


def rule_tradeoffs(options: list[dict]) -> dict[str, dict]:
    """Deterministic pros/cons used when no language model is available, and as grounding facts."""
    out = {}
    costs = [o["cost"]["total"] for o in options]
    pax = [passenger_index(o["metrics"]) for o in options]
    rec = [o["metrics"]["recovery_min"] for o in options]
    for i, o in enumerate(options):
        m = o["metrics"]
        pros, cons = [], []
        if costs[i] == min(costs):
            pros.append("Lowest total recovery cost of all options")
        if costs[i] == max(costs):
            cons.append("Highest total recovery cost")
        if pax[i] == min(pax):
            pros.append("Least disruption to passengers overall")
        if rec[i] == min(rec):
            pros.append("Fastest return to normal schedule")
        if rec[i] == max(rec) and len(set(rec)) > 1:
            cons.append("Slowest return to normal schedule")
        if m["trips_cancelled"] == 0:
            pros.append("No service cancellations")
        else:
            cons.append(f"Cancels {m['trips_cancelled']} services")
        if m["pax_unaccommodated"]:
            cons.append(f"{m['pax_unaccommodated']} passengers cannot be re-accommodated within 18 h")
        if m["crew_unresolved"]:
            cons.append(f"{m['crew_unresolved']} crew pairings breach duty limits without reserve cover")
        elif m["reserve_crew_used"]:
            cons.append(f"Calls out {m['reserve_crew_used']} reserve crew")
        if o["repair_dependent"]:
            cons.append("Outcome depends on the repair window holding")
        else:
            pros.append("Independent of repair-window uncertainty")
        if m["avg_delay_min"] and m["avg_delay_min"] <= 60:
            pros.append(f"Average delay held to {m['avg_delay_min']} min")
        elif m["avg_delay_min"] > 120:
            cons.append(f"Average delay of {m['avg_delay_min']} min on affected services")
        explanation = (f"{o['name']} affects {m['pax_affected']} passengers, delays {m['trips_delayed']} services "
                       f"(average {m['avg_delay_min']} min) and cancels {m['trips_cancelled']}. "
                       f"Estimated cost is {fmt_inr(o['cost']['total'])} with the network recovered in about "
                       f"{m['recovery_min'] // 60} h {m['recovery_min'] % 60} min.")
        out[o["id"]] = {"pros": pros[:4], "cons": cons[:4], "explanation": explanation}
    return out


def fmt_inr(amount: float) -> str:
    if amount >= 1e7:
        return f"INR {amount / 1e7:.2f} Cr"
    if amount >= 1e5:
        return f"INR {amount / 1e5:.1f} L"
    return f"INR {amount:,.0f}"


def hours_until(dt: datetime) -> float:
    return (dt - now()).total_seconds() / 3600
