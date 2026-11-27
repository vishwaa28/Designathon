"""Crowd monitor service: frame analysis with the vision model, rolling state per camera and reroute advisories."""
from __future__ import annotations

import logging
import threading
import time
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
          "frame and describe how the queue is moving. You never invent people who are not visible.")


def _prompt(cam: dict, terminal: dict) -> str:
    return (
        f"Camera: {cam['name']} ({cam['zone']}), {terminal['name']} departures. It watches a passenger security queue.\n"
        "Count every person visible in this frame, including people partly hidden behind others whose head or shoulders "
        "can be seen. Do not count people shown on screens or in reflections.\n"
        "Method: split the image into three depth bands (foreground, midground, background), count each band, then add them.\n"
        "Then work out how many of them stand in the queuing lanes (exclude staff and people simply walking across), how many "
        "separate queue lanes are visible, and whether the queue is flowing, slow or stationary.\n"
        'Return JSON: {"foreground": int, "midground": int, "background": int, "people_total": int, '
        '"people_in_queue": int, "queue_lanes": int, "movement": "flowing|slow|stationary", '
        '"confidence": a number between 0 and 1}'
    )


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
    base = {
        "id": cam["id"], "name": cam["name"], "zone": cam["zone"], "terminal_id": cam["terminal"], "video": cam["video"],
        "area_m2": cam["area_m2"], "service_points": cam["service_points"], "rate_per_point": cam["rate_per_point"],
        "alternate": cam.get("alternate"), "throughput_per_min": round(cw.throughput(cam), 1),
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
        "density": density, "level": cw.density_level(density), "wait_min": cw.wait_minutes(sm["people_in_queue"], cam),
        "observed_at": rows[-1]["observed_at"], "age_s": age, "latency_ms": rows[-1].get("latency_ms"),
        "history": [{"t": r["observed_at"], "people": r["people_total"], "queue": r["people_in_queue"], "wait": r["wait_min"]}
                    for r in rows],
    }


def overview() -> dict:
    out = []
    for t in ref.TERMINALS:
        cams = [camera_state(c) for c in cameras(t["id"])]
        out.append({**cw.rollup(t, cams), "cameras": cams, "plan": cw.build_plan(cams)})
    return {
        "terminals": out,
        "vision": {"provider": llm.active, "model": llm.model_for(llm.active), "configured": llm.is_configured(llm.active)},
        "frame_interval_s": settings.crowd_frame_interval_s,
        "updated_at": iso(now()),
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


# ---- reroute -----------------------------------------------------------------------------
def _terminal_departures(terminal_id: str) -> list[dict]:
    """Hub departures from this terminal's gates in the next window. Caller holds store.lock."""
    t0, t1 = add_min(now(), 10), add_min(now(), FLIGHT_WINDOW_MIN)
    rows = []
    for t in store.trips.values():
        if t["origin"] != ref.HUB_AIRPORT or t["cancelled"] or t["diverted_to"]:
            continue
        if t["gate"].split("-")[0] != terminal_id:
            continue
        if t0 <= store.est_dep(t) <= t1:
            rows.append(t)
    return sorted(rows, key=store.est_dep)


def _flight_rows(terminal_id: str, wait_now: float, wait_after: float) -> list[dict]:
    out = []
    now_dt = now()
    for t in _terminal_departures(terminal_id):
        mins = (store.est_dep(t) - now_dt).total_seconds() / 60
        pax = store.pax_by_trip.get(t["id"], set())
        slack = cw.risk_slack(mins, wait_now)
        out.append({
            "trip_id": t["id"], "number": t["number"], "destination": ref.city_of(t["destination"]),
            "gate": t["gate"], "departs": iso(store.est_dep(t)), "minutes_to_departure": int(mins),
            "passengers": len(pax), "contacts": sum(1 for pid in pax if store.passengers[pid].get("contact")),
            "slack_min": int(slack), "slack_after_min": int(cw.risk_slack(mins, wait_after)),
            "at_risk": slack < 10,
        })
    return out


def plan(terminal_id: str) -> dict:
    t = terminal(terminal_id)
    cams = [camera_state(c) for c in cameras(terminal_id)]
    p = cw.build_plan(cams)
    live = [c for c in cams if c["status"] != "no_data"]
    wait_now = max((c["wait_min"] for c in live), default=0)
    wait_after = p.get("target_wait_min", 0) if live else 0
    if p.get("rebalance"):
        wait_after = max(p["rebalance"]["projected"].values())
    with store.lock:
        flights = _flight_rows(terminal_id, wait_now, wait_after)
        window = {t["id"] for t in _terminal_departures(terminal_id)}
        contacts = contact_dir.earliest_per_contact(trip_ids=window)
        at_risk_pax = ({pid for f in flights if f["at_risk"] for pid in store.pax_by_trip[f["trip_id"]]}
                       - set(contact_dir.all_contact_ids()))
    recipients = len(at_risk_pax) + len(contacts)
    return {
        "terminal": {"id": t["id"], "name": t["name"]}, **p,
        "wait_now_min": wait_now, "wait_after_min": wait_after,
        "flights": flights,
        "recipients": {"total": recipients, "at_risk": len(at_risk_pax), "contacts": len(contacts),
                       "real_channels": len(contacts)},
        "history": db.recent_reroutes(terminal_id, 8),
    }


def _message(p: dict, trip: dict, plan_: dict, cams: dict[str, dict], at_risk: bool, buffer_min: int) -> tuple[str, str]:
    t_cfg = plan_["terminal"]["name"]
    target = cams.get(plan_.get("target_camera"))
    worst = max(cams.values(), key=lambda c: c["wait_min"])
    dep = store.est_dep(trip).strftime("%H:%M")
    lead = ("Your flight is close to the gate closing time" if at_risk else "A heads-up before you travel")
    use = (f"Please use {target['name']} (about {target['wait_min']:.0f} min wait) and " if target and target["id"] != worst["id"]
           else "Please ")
    message = (f"{lead}: security queues at {t_cfg} are long right now ({worst['name']}: about {worst['wait_min']:.0f} min). "
               f"{use}reach security at least {buffer_min} minutes before {trip['number']} departs at {dep}.")
    return f"{t_cfg} security queue advisory", message


def send_reroute(terminal_id: str, force: bool = False) -> dict:
    t = terminal(terminal_id)
    cams_state = [camera_state(c) for c in cameras(terminal_id)]
    p = cw.build_plan(cams_state)
    if p["status"] == "no_data":
        raise CrowdError("No camera data yet. Wait for the first analysed frames.", 409)
    if p["status"] == "normal" and not force:
        raise CrowdError("Crowd levels are normal, so no advisory is needed.", 409)
    cams = {c["id"]: c for c in cams_state if c["status"] != "no_data"}
    wait_now = max(c["wait_min"] for c in cams.values())
    wait_after = max(p["rebalance"]["projected"].values()) if p.get("rebalance") else p["target_wait_min"]
    buffer_min = int(ref.GATE_CLOSE_BUFFER_MIN + wait_after + 10)
    plan_ = {"terminal": {"id": t["id"], "name": t["name"]}, "target_camera": p["target_camera"]}

    sent_at = iso(now())
    records, outbound = [], []
    with store.lock:
        flights = _flight_rows(terminal_id, wait_now, wait_after)
        risk_ids = {f["trip_id"] for f in flights if f["at_risk"]}
        pax_ids = {pid for tid in risk_ids for pid in store.pax_by_trip[tid]}
        # Contact travelers are booked on every flight: each gets one advisory, for their soonest departure here.
        window = {t["id"] for t in _terminal_departures(terminal_id)}
        chosen = contact_dir.earliest_per_contact(trip_ids=window)
        placed = []
        for pid in chosen:
            c = store.passengers[pid]
            placed.append({"pnr": c["pnr"], "name": f"{c['first_name']} {c['last_name']}",
                           "trip": store.trips[c["legs"][0]]["number"]})
        simulated = sorted(pax_ids - set(contact_dir.all_contact_ids()),
                           key=lambda pid: (not is_priority(store.passengers[pid]), pid))
        for pid in simulated[:MAX_SIMULATED_RECIPIENTS] + chosen:
            x = store.passengers[pid]
            trip = store.trips[x["legs"][0]]
            subject, text = _message(x, trip, plan_, cams, trip["id"] in risk_ids, buffer_min)
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
    src = p["rebalance"]["from"] if p.get("rebalance") else max(cams.values(), key=lambda c: c["wait_min"])["id"]
    summary = (f"Advisory to {len(records)} travelers on {len(risk_ids)} at-risk departures "
               f"({len(outbound)} real e-mail/SMS recipients). Longest wait {wait_now:.0f} min.")
    entry = {"terminal_id": terminal_id, "from_camera": src, "to_camera": p["target_camera"], "passengers": len(records),
             "contacts": len(outbound), "flights": [f["number"] for f in flights if f["at_risk"]], "summary": summary,
             "delivery": counts}
    db.save_reroute(entry)
    bus.publish("crowd.reroute", {"terminal_id": terminal_id, "passengers": len(records)})
    return {"sent_at": sent_at, "summary": summary, "recipients": len(records), "at_risk_flights": len(risk_ids),
            "contacts": [{**c, "status": next((r["status"] for r, _, _ in outbound if r["pnr"] == c["pnr"]), None)} for c in placed],
            "delivery": counts, "plan": p}
