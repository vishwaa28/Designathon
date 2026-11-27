"""Crowd monitor service: frame analysis with the vision model, rolling state per camera and reroute advisories."""
from __future__ import annotations

import logging
import threading
import time
from datetime import timedelta

from app.config import settings
from app.core.events import bus
from app.core.llm import llm
from app.core.utils import add_min, iso, now, parse_dt
from app.data import db
from app.data import reference as ref
from app.data.store import is_priority, store
from app.domain import contacts as contact_dir
from app.domain import crowd as cw
from app.domain import notifications as nt
from app.services import delivery

log = logging.getLogger("arro.crowd")

MIN_INTERVAL_S = 5               # a camera is analysed at most this often, whoever asks
MAX_IMAGE_BYTES = 1_500_000
FLIGHT_WINDOW_MIN = 150          # departures considered for advisories
MAX_SIMULATED_RECIPIENTS = 400
_last_run: dict[str, float] = {}
_run_lock = threading.Lock()


class CrowdError(Exception):
    def __init__(self, message: str, status: int = 502) -> None:
        super().__init__(message)
        self.status = status


SYSTEM = ("You are a computer-vision crowd analytics service for airport operations. You count people in a single CCTV "
          "frame and describe how they are moving. You never invent people who are not visible.")

_COUNTING = ("Count every person visible in this frame, including people partly hidden behind others whose head or shoulders "
             "can be seen. Do not count people shown on screens or in reflections.\n"
             "Method: split the image into three depth bands (foreground, midground, background), count each band, then add them.\n")
_SCHEMA = ('Return JSON: {"foreground": int, "midground": int, "background": int, "people_total": int, '
           '"people_in_queue": int, "queue_lanes": int, "movement": "flowing|slow|stationary", '
           '"confidence": a number between 0 and 1}')

_KIND_BRIEF = {
    "security": ("It watches a passenger security queue.\n",
                 "Then work out how many of them stand in the queuing lanes (people_in_queue; exclude staff and people simply "
                 "walking across), how many separate queue lanes are visible (queue_lanes), and whether the queue is flowing, "
                 "slow or stationary (movement).\n"),
    "concourse": ("It watches a busy departures concourse where passengers walk towards the security checkpoints.\n",
                  "Then work out how many of them are travelling passengers in the main stream heading towards security "
                  "(people_in_queue; exclude staff, people seated and shop or desk staff), how many separate parallel streams "
                  "you can see (queue_lanes) and whether the crowd is flowing, slow or stationary (movement).\n"),
    "lounge": ("It watches a seated waiting area at the boarding gates.\n",
               "Then work out how many of them are standing rather than seated (people_in_queue), use 0 for queue_lanes, and "
               "say whether people are mostly settled (stationary), drifting (slow) or moving about (flowing) for movement.\n"),
}


def _prompt(cam: dict, terminal: dict) -> str:
    intro, tail = _KIND_BRIEF[cw.kind_of(cam)]
    return f"Camera: {cam['name']} ({cam['zone']}), {terminal['name']} departures. {intro}{_COUNTING}{tail}{_SCHEMA}"


def cameras(terminal_id: str | None = None) -> list[dict]:
    return [c for c in ref.CAMERAS if terminal_id is None or c["terminal"] == terminal_id]


def camera(camera_id: str) -> dict:
    cam = next((c for c in ref.CAMERAS if c["id"] == camera_id), None)
    if cam is None:
        raise CrowdError("Unknown camera", 404)
    return cam


def terminal(terminal_id: str) -> dict:
    t = next((t for t in ref.TERMINALS if t["id"] == terminal_id), None)
    if t is None:
        raise CrowdError("Unknown terminal", 404)
    return t


def _rows(camera_id: str, limit: int = 30) -> list[dict]:
    rows = db.recent_observations(camera_id, limit)
    for r in rows:
        r["_ts"] = parse_dt(r["observed_at"]).timestamp()
    return rows


def camera_state(cam: dict) -> dict:
    rows = _rows(cam["id"])
    kind = cw.kind_of(cam)
    security = kind == "security"
    base = {
        "id": cam["id"], "kind": kind, "name": cam["name"], "zone": cam["zone"], "terminal_id": cam["terminal"],
        "video": cam["video"], "area_m2": cam["area_m2"], "seats": cam.get("seats"),
        "service_points": cam.get("service_points"), "rate_per_point": cam.get("rate_per_point"),
        "alternate": cam.get("alternate"), "fast_track": bool(cam.get("fast_track")),
        "throughput_per_min": round(cw.throughput(cam), 1) if security else None,
    }
    sm = cw.smooth(rows)
    if sm is None:
        return {**base, "status": "no_data", "people_total": 0, "people_in_queue": 0, "queue_lanes": None, "movement": None,
                "confidence": None, "density": 0, "level": "LOW", "wait_min": 0, "observed_at": None, "age_s": None,
                "samples": 0, "latency_ms": None, "history": []}
    density = round(sm["people_total"] / cam["area_m2"], 2)
    age = max(0, int(time.time() - rows[-1]["_ts"]))
    return {
        **base, **sm,
        "status": "live" if age <= cw.STALE_AFTER_S else "stale",
        "density": density, "level": cw.density_level(density, kind),
        "wait_min": cw.wait_minutes(sm["people_in_queue"], cam) if security else 0.0,
        "observed_at": rows[-1]["observed_at"], "age_s": age, "latency_ms": rows[-1].get("latency_ms"),
        "history": [{"t": r["observed_at"], "people": r["people_total"], "queue": r["people_in_queue"], "wait": r["wait_min"]}
                    for r in rows],
    }


def analyze_frame(camera_id: str, image_b64: str, mime: str = "image/jpeg") -> dict:
    cam = camera(camera_id)
    t = terminal(cam["terminal"])
    if len(image_b64) * 3 // 4 > MAX_IMAGE_BYTES:
        raise CrowdError("Frame is too large", 413)
    with _run_lock:
        if time.monotonic() - _last_run.get(camera_id, 0) < MIN_INTERVAL_S:
            return {**camera_state(cam), "throttled": True}
        _last_run[camera_id] = time.monotonic()
    raw, call = llm.complete_vision_json(SYSTEM, _prompt(cam, t), image_b64, mime=mime, purpose="Crowd analysis")
    if raw is None:
        raise CrowdError(f"Vision model unavailable: {call.error or 'no answer'}", 503)
    obs = cw.validate(raw)
    if obs is None:
        raise CrowdError("The vision model returned no usable head count", 502)
    metrics = cw.observation_metrics(cam, obs)
    db.save_observation({**obs, **metrics, "camera_id": cam["id"], "terminal_id": t["id"], "observed_at": iso(now()),
                         "model": f"{call.provider}/{call.model}", "latency_ms": call.latency_ms})
    bus.publish("crowd.updated", {"camera_id": cam["id"], "terminal_id": t["id"], "people_total": obs["people_total"]})
    return camera_state(cam)


# ---- departures and plan -----------------------------------------------------------------
def _departures(terminal_id: str) -> list[dict]:
    """Hub departures from this terminal's gates in the coming window, as plain rows."""
    t0, t1 = add_min(now(), 10), add_min(now(), FLIGHT_WINDOW_MIN)
    now_dt = now()
    rows = []
    with store.lock:
        for t in store.trips.values():
            if t["origin"] != ref.HUB_AIRPORT or t["cancelled"] or t["diverted_to"]:
                continue
            if t["gate"].split("-")[0] != terminal_id or not (t0 <= store.est_dep(t) <= t1):
                continue
            pax = store.pax_by_trip.get(t["id"], set())
            rows.append({
                "trip_id": t["id"], "number": t["number"], "destination": ref.city_of(t["destination"]), "gate": t["gate"],
                "departs": iso(store.est_dep(t)), "_dep": store.est_dep(t),
                "minutes_to_departure": (store.est_dep(t) - now_dt).total_seconds() / 60,
                "passengers": len(pax), "contacts": sum(1 for pid in pax if store.passengers[pid].get("contact")),
            })
    rows.sort(key=lambda r: r["_dep"])
    return rows


def _build(terminal_id: str) -> tuple[list[dict], dict, list[dict]]:
    cams = [camera_state(c) for c in cameras(terminal_id)]
    deps = _departures(terminal_id)
    return cams, cw.build_plan(cams, deps), deps


def _flight_rows(deps: list[dict], plan_: dict) -> list[dict]:
    """Departures with the plan's guidance: slack with and without the plan, checkpoint, lane and arrive-by time."""
    now_dt = now()
    out = []
    for d in deps:
        g = plan_["flights"].get(d["trip_id"]) if plan_["status"] != "no_data" else None
        row = {k: v for k, v in d.items() if k != "_dep"}
        row["minutes_to_departure"] = int(d["minutes_to_departure"])
        if g:
            when = now_dt + timedelta(minutes=max(0, g["arrive_in_min"]))
            row.update({
                "slack_min": g["slack_now_min"], "slack_after_min": g["slack_after_min"],
                "at_risk": g["slack_now_min"] < 10, "priority": g["priority"],
                "checkpoint": g["checkpoint"], "lane": g["lane"], "expected_wait_min": g["expected_wait_min"],
                "arrive_in_min": max(0, g["arrive_in_min"]), "arrive_by": iso(when),
            })
        else:
            row.update({"slack_min": None, "slack_after_min": None, "at_risk": False, "priority": False, "checkpoint": None,
                        "lane": None, "expected_wait_min": None, "arrive_in_min": None, "arrive_by": None})
        out.append(row)
    return out


def overview() -> dict:
    out = []
    for t in ref.TERMINALS:
        cams, p, _ = _build(t["id"])
        out.append({**cw.rollup(t, cams), "cameras": cams, "plan": {k: v for k, v in p.items() if k != "flights"}})
    return {
        "terminals": out,
        "vision": {"provider": llm.active, "model": llm.model_for(llm.active), "configured": llm.is_configured(llm.active)},
        "frame_interval_s": settings.crowd_frame_interval_s,
        "updated_at": iso(now()),
    }


def _recipients(p: dict, rows: list[dict]) -> tuple[list[str], list[str]]:
    """(simulated passenger ids, contact passenger ids) for the advisory. Caller holds store.lock."""
    helped = {r["trip_id"] for r in rows if r["at_risk"] or r["priority"]}
    pax = {pid for tid in helped for pid in store.pax_by_trip[tid]}
    simulated = sorted(pax - set(contact_dir.all_contact_ids()),
                       key=lambda pid: (not is_priority(store.passengers[pid]), pid))
    chosen = contact_dir.earliest_per_contact(trip_ids={r["trip_id"] for r in rows})
    return simulated, chosen


def plan(terminal_id: str) -> dict:
    t = terminal(terminal_id)
    cams, p, deps = _build(terminal_id)
    rows = _flight_rows(deps, p)
    with store.lock:
        simulated, chosen = _recipients(p, rows)
    return {
        "terminal": {"id": t["id"], "name": t["name"]}, **{k: v for k, v in p.items() if k != "flights"},
        "flights": rows,
        "recipients": {"total": len(simulated) + len(chosen), "at_risk": len(simulated), "contacts": len(chosen),
                       "real_channels": len(chosen)},
        "history": db.recent_reroutes(terminal_id, 8),
    }


def _message(trip: dict, row: dict, p: dict, terminal_name: str) -> tuple[str, str]:
    dep = store.est_dep(trip).strftime("%H:%M")
    unguided = p["outlook"]["unguided_wait_min"]
    where = row["checkpoint"] + (f" ({row['lane']})" if row["lane"] else "")
    by = f"by {parse_dt(row['arrive_by']).strftime('%H:%M')}" if row["arrive_in_min"] else "now"
    lead = "Your flight is close to the gate closing time" if (row["at_risk"] or row["priority"]) else "A heads-up before you travel"
    message = (f"{lead}: security at {terminal_name} is busy (up to about {unguided:.0f} min in the longest queue). "
               f"For {trip['number']} (departs {dep}) please go to {where}, where the wait is about "
               f"{row['expected_wait_min']:.0f} min, and be at security {by}.")
    return f"{terminal_name} security queue advisory", message


def send_reroute(terminal_id: str, force: bool = False) -> dict:
    t = terminal(terminal_id)
    cams_state, p, deps = _build(terminal_id)
    if p["status"] == "no_data":
        raise CrowdError("No camera data yet. Wait for the first analysed frames.", 409)
    if p["status"] == "normal" and not force:
        raise CrowdError("Crowd levels are normal, so no advisory is needed.", 409)
    rows = _flight_rows(deps, p)
    by_trip = {r["trip_id"]: r for r in rows}
    security = [c for c in cams_state if c["kind"] == "security" and c["status"] != "no_data"]

    sent_at = iso(now())
    records, outbound = [], []
    with store.lock:
        simulated, chosen = _recipients(p, rows)
        placed = []
        for pid in chosen:
            c = store.passengers[pid]
            placed.append({"pnr": c["pnr"], "name": f"{c['first_name']} {c['last_name']}",
                           "trip": store.trips[c["legs"][0]]["number"]})
        for pid in simulated[:MAX_SIMULATED_RECIPIENTS] + chosen:
            x = store.passengers[pid]
            trip = store.trips[x["legs"][0]]
            row = by_trip.get(trip["id"])
            if row is None or row["checkpoint"] is None:
                continue
            subject, text = _message(trip, row, p, t["name"])
            rec = {
                "id": store.next_id("NTF", 100001), "incident_id": None, "pax_id": pid, "pnr": x["pnr"],
                "name": f"{x['first_name']} {x['last_name']}", "last_name": x["last_name"], "language": "en",
                "language_label": "English", "channel": x["channel"], "outcome": "CROWD_ADVISORY", "subject": subject,
                "message": text, "priority": is_priority(x), "escalation": None, "trip": trip["number"], "new_trip": None,
                "status": "DELIVERED", "sent_at": sent_at,
                "self_service_url": nt.portal_link(x["pnr"], x["last_name"]) if x.get("contact") else None,
                "contact": bool(x.get("contact")),
            }
            records.append(rec)
            if x.get("contact"):
                outbound.append((rec, dict(x), None))
        store.notifications.extend(records)
    counts = delivery.deliver_many(outbound) if outbound else {"email_sent": 0, "sms_sent": 0, "failed": 0,
                                                              "not_configured": 0, "recipients": 0}
    helped = [r for r in rows if r["at_risk"] or r["priority"]]
    src = max(security, key=lambda c: c["wait_min"])["id"]
    out = p["outlook"]
    summary = (f"Advisory to {len(records)} travelers on {len(helped)} departures ({len(outbound)} real e-mail/SMS recipients). "
               f"Longest wait {out['unguided_wait_min']:.0f} min unguided, about {out['planned_wait_min']:.0f} min with the plan.")
    entry = {"terminal_id": terminal_id, "from_camera": src, "to_camera": p["target_camera"], "passengers": len(records),
             "contacts": len(outbound), "flights": [r["number"] for r in helped], "summary": summary, "delivery": counts}
    db.save_reroute(entry)
    bus.publish("crowd.reroute", {"terminal_id": terminal_id, "passengers": len(records)})
    return {"sent_at": sent_at, "summary": summary, "recipients": len(records), "at_risk_flights": len(helped),
            "contacts": [{**c, "status": next((r["status"] for r, _, _ in outbound if r["pnr"] == c["pnr"]), None)} for c in placed],
            "delivery": counts, "plan": {k: v for k, v in p.items() if k != "flights"}}
