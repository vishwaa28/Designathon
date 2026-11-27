"""End-to-end workflow smoke test.

Usage (from server/):  python -m tests.smoke_test [--llm]
Without --llm every agent runs on its rule-based fallback, which keeps the run fast and offline.
"""
from __future__ import annotations

import os
import sys
import time

os.environ.setdefault("AGENT_STEP_DELAY_SECONDS", "0")

from app.core.llm import llm  # noqa: E402
from app.data.store import store  # noqa: E402
from app.services import feeds, orchestrator  # noqa: E402

if "--llm" not in sys.argv:
    llm.is_configured = lambda provider: False  # type: ignore[method-assign]


def wait_for(incident_id: str, statuses: set[str], timeout: float = 240) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        inc = store.incidents[incident_id]
        if inc["status"] in statuses:
            return inc
        if inc["status"] == "FAILED":
            raise RuntimeError(inc["error"])
        time.sleep(0.2)
    raise TimeoutError(f"{incident_id} stuck in {store.incidents[incident_id]['status']}")


def run(scenario_id: str) -> None:
    t0 = time.time()
    inc = orchestrator.trigger_scenario(scenario_id)
    iid = inc["id"]
    inc = wait_for(iid, {"AWAITING_APPROVAL", "NO_ACTION"})
    s = inc["impact"]["summary"]
    print(f"\n== {scenario_id} -> {iid} [{inc['severity']}] {time.time() - t0:.1f}s")
    print(f"   impact: {s['trips_direct']} direct + {s['trips_cascade']} cascade services, {s['pax_affected']} pax, "
          f"{s['missed_connections']} missed conn, {s['crew_pairings_breached']} crew breaches, {s['priority_pax']} priority")
    print(f"   restoration: {inc['infra']['restoration']}  WO {inc['work_order_id']}")
    for o in inc["options"]:
        m = o["metrics"]
        print(f"   {o['id']} {o['name']:<28} score {o['score']:>3} conf {o['confidence']:.2f} cost {o['cost']['total']:>11,} "
              f"delayed {m['trips_delayed']:>2} cancel {m['trips_cancelled']:>2} rebooked {m['pax_rebooked']:>4} "
              f"unacc {m['pax_unaccommodated']:>3} {'*' if o['recommended'] else ''}")

    orchestrator.push_update(iid, "restoration_delayed", "smoke")
    inc = wait_for(iid, {"AWAITING_APPROVAL"})
    print(f"   after update v{inc['plan_version']}: recommended {inc['recommendation']['option_id']} "
          f"restoration {inc['infra']['restoration']['p50'][11:16]}")

    orchestrator.submit_decision(iid, {"action": "replan", "controller": "smoke",
                                       "preferences": {"priority": "cost", "max_delay_min": 180}})
    inc = wait_for(iid, {"AWAITING_APPROVAL"})
    rec = inc["recommendation"]["option_id"]
    print(f"   after replan v{inc['plan_version']}: recommended {rec}")

    orchestrator.submit_decision(iid, {"action": "approve", "option_id": rec, "controller": "smoke"})
    inc = wait_for(iid, {"RESOLVED"})
    n = inc["notifications"]
    print(f"   notified {n['total']} ({n['by_language']}) changes {n['plan_changes']}")
    print(f"   trace: {[(e['node'], e['status']) for e in inc['trace']]}")
    calls = [c for e in inc["trace"] for c in e["llm"]]
    for c in calls:
        print(f"   llm {c['provider']}/{c['model']} {c['purpose']:<26} ok={c['ok']} {c['latency_ms']} ms {c['error'] or ''}")
    if calls and "--llm" in sys.argv:
        print(f"   sample message: {store.notifications[-1]['message']}")
        print(f"   rationale: {inc['recommendation']['rationale']}")


if __name__ == "__main__":
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    for sc in feeds.SCENARIOS:
        if only is None or sc["id"] == only:
            run(sc["id"])
    print("\nAll scenarios completed.")
