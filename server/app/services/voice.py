"""Traveler voice assistant: bridges a browser audio WebSocket to Azure Voice Live.

The browser streams 24 kHz mono PCM16 microphone audio to this service; the service relays it to
Voice Live (API key auth, no DefaultAzureCredential), plays back synthesised speech and executes the
assistant's tool calls (booking status, alternatives, rebook, refund) against the same self-service logic
the portal uses. The API key never leaves the server.
"""
from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import logging
from urllib.parse import urlparse

from azure.ai.voicelive.aio import connect
from azure.ai.voicelive.models import (
    AudioEchoCancellation,
    AudioInputTranscriptionOptions,
    AudioNoiseReduction,
    AzureStandardVoice,
    FunctionCallOutputItem,
    FunctionTool,
    InputAudioFormat,
    InputTextContentPart,
    Modality,
    OutputAudioFormat,
    RequestSession,
    ServerEventType,
    ServerVad,
    UserMessageItem,
)
from azure.core.credentials import AzureKeyCredential
from fastapi import HTTPException, WebSocket, WebSocketDisconnect

from app.api import traveler
from app.config import settings
from app.core.events import bus
from app.core.utils import parse_dt
from app.services import delivery
from app.data import reference as ref
from app.data.store import store

log = logging.getLogger("arro.voice")

LANGUAGES = {
    "en": {"label": "English", "native": "English", "locale": "en-IN", "voice": "en-IN-NeerjaNeural", "stt": "en-IN"},
    "ta": {"label": "Tamil", "native": "தமிழ்", "locale": "ta-IN", "voice": "ta-IN-PallaviNeural", "stt": "ta-IN"},
    "te": {"label": "Telugu", "native": "తెలుగు", "locale": "te-IN", "voice": "te-IN-ShrutiNeural", "stt": "te-IN"},
}

HELP_DESK = "1800 200 4040"

TOOLS = [
    FunctionTool(
        name="get_booking_status",
        description="Get the passenger's current itinerary with live status, delays and which legs need action.",
        parameters={"type": "object", "properties": {}, "required": []},
    ),
    FunctionTool(
        name="get_alternatives",
        description="List alternative services with open seats (same city pair, next 24 hours, flights or trains) for one leg of the booking.",
        parameters={
            "type": "object",
            "properties": {"leg_id": {"type": "string", "description": "Leg id from the booking, e.g. MR107"}},
            "required": ["leg_id"],
        },
    ),
    FunctionTool(
        name="rebook",
        description="Move the passenger from one leg to a chosen alternative. Only call after the passenger has clearly confirmed the exact service.",
        parameters={
            "type": "object",
            "properties": {
                "leg_id": {"type": "string", "description": "Leg being replaced"},
                "new_trip_id": {"type": "string", "description": "Alternative service id returned by get_alternatives"},
            },
            "required": ["leg_id", "new_trip_id"],
        },
    ),
    FunctionTool(
        name="request_refund",
        description="Cancel one leg and start a full refund. Only call after the passenger has clearly confirmed they want a refund.",
        parameters={
            "type": "object",
            "properties": {"leg_id": {"type": "string", "description": "Leg to cancel and refund"}},
            "required": ["leg_id"],
        },
    ),
]


def voice_status() -> dict:
    return {
        "configured": bool(settings.voice_endpoint and settings.voice_api_key),
        "model": settings.voice_model,
        "languages": [{"id": k, "label": v["label"], "native": v["native"]} for k, v in LANGUAGES.items()],
    }


def _resource_endpoint() -> str:
    parsed = urlparse(settings.voice_endpoint or "")
    return f"{parsed.scheme}://{parsed.netloc}/"


def _clock(iso_value: str) -> str:
    return parse_dt(iso_value).strftime("%H:%M")


def _leg_line(v: dict) -> str:
    when = f"departs {_clock(v['est_dep'])}, arrives {_clock(v['est_arr'])}"
    extra = f", delayed {v['delay_min']} min" if v["delay_min"] else ""
    return (f"- leg_id={v['id']}: {v['number']} {v['origin_city']} to {v['destination_city']}, {when}{extra}, "
            f"status {v['status'].replace('_', ' ').lower()}, {'gate' if v['mode'] == 'FLIGHT' else 'platform'} {v['gate']}")


def _booking_snapshot(p: dict) -> dict:
    view = store.pax_view(p)
    disruptions = []
    for tid in p["legs"]:
        for inc_id in store.trips[tid]["disruption_ids"]:
            inc = store.incidents.get(inc_id)
            if inc and inc["title"] not in disruptions:
                disruptions.append(inc["title"])
    return {
        "passenger": view,
        "actionable_leg_ids": traveler.actionable_legs(p),
        "disruption": disruptions,
    }


def build_instructions(p: dict, lang: str) -> str:
    cfg = LANGUAGES[lang]
    snap = _booking_snapshot(p)
    v = snap["passenger"]
    legs = "\n".join(_leg_line(leg) for leg in v["legs"]) or "- (no active legs: booking refunded)"
    needs = ", ".join(snap["actionable_leg_ids"]) or "none"
    special = {"WCHR": "wheelchair assistance", "UMNR": "unaccompanied minor", "MEDA": "medical assistance",
               "SRCT": "senior citizen"}.get(v["ssr"], "")
    return f"""You are the voice assistant of Meridian Airways and Southern Rail, helping one traveler manage a disrupted journey by phone-style conversation.

LANGUAGE: Speak and understand {cfg['label']} ({cfg['locale']}). Always answer in {cfg['label']}, using natural, polite, everyday wording. Keep flight numbers, train numbers, airport codes and times in their standard form (for example "MR 107", "MAA", "18:30"). Speak numbers clearly.

STYLE: This is spoken audio. Use one to three short sentences per turn, no lists, no markdown, no emojis. Warm, calm and reassuring: travelers are worried. Ask one question at a time.

PASSENGER: {v['name']} (address as {v['first_name']}), booking {v['pnr']}, {v['cabin'].lower()} cabin{', ' + v['tier'].lower() + ' member' if v['tier'] else ''}{', requires ' + special if special else ''}.
Current time context: services below show live estimates.
ITINERARY:
{legs}
Legs that need action: {needs}.
Known disruption: {'; '.join(snap['disruption']) or 'none recorded'}.

WHAT YOU CAN DO
- Explain what happened to the journey and the new timings using only the facts above or tool results.
- Offer alternatives with get_alternatives and read out at most three options (service number, departure time, arrival time, seats left, and mention if it is a train or flight alternative).
- Rebook with rebook, or start a refund with request_refund.

RULES
- Never invent times, services, fares or policies. If unsure, call get_booking_status or say you will connect them to the help desk on {HELP_DESK}.
- Before rebooking or refunding, repeat the exact service or action and wait for a clear yes. Never change a booking without that confirmation.
- After a successful change, confirm the new service and departure time in one sentence.
- You only discuss this booking and its disruption. Politely decline anything else.
- If the traveler seems distressed, needs medical help, or insists on a person, give the help desk number {HELP_DESK}."""


def _greeting_instruction(p: dict, lang: str) -> str:
    cfg = LANGUAGES[lang]
    needs = traveler.actionable_legs(p)
    focus = ("Briefly say that you can see their journey has been affected and ask how you can help, for example by explaining "
             "the change or finding another option." if needs else
             "Say you can help with their trip status or changes, and ask how you can help.")
    return (f"Greet {p['first_name']} warmly in {cfg['label']} as the Meridian and Southern Rail assistant. {focus} "
            f"Keep it to two short sentences.")


# ---- tool execution ----------------------------------------------------------

def _confirm(record: dict, p: dict) -> None:
    if p.get("contact"):
        delivery.dispatch(record, p)


def _run_tool(p: dict, name: str, args: dict) -> tuple[dict, str | None]:
    """Execute a tool against the store. Returns (result, event_to_publish)."""
    try:
        with store.lock:
            if name == "get_booking_status":
                snap = _booking_snapshot(p)
                return {"passenger_status": snap["passenger"]["status"], "legs": [
                    {"leg_id": leg["id"], "service": leg["number"], "from": leg["origin_city"], "to": leg["destination_city"],
                     "departs": _clock(leg["est_dep"]), "arrives": _clock(leg["est_arr"]), "delay_min": leg["delay_min"],
                     "status": leg["status"]} for leg in snap["passenger"]["legs"]],
                        "legs_needing_action": snap["actionable_leg_ids"]}, None
            if name == "get_alternatives":
                res = traveler.find_alternatives(p, args.get("leg_id", ""))
                return {"options": [
                    {"new_trip_id": t["id"], "service": t["number"], "mode": "train" if t["mode"] == "TRAIN" else "flight",
                     "departs": _clock(t["est_dep"]), "arrives": _clock(t["est_arr"]), "seats_left": t["seats_left"],
                     "different_mode": t["alt_mode"]} for t in res["items"][:5]]}, None
            if name == "rebook":
                record = traveler.apply_rebook(p, args.get("leg_id", ""), args.get("new_trip_id", ""))
                _confirm(record, p)
                return {"ok": True, "confirmation": record["message"]}, "traveler.rebooked"
            if name == "request_refund":
                record = traveler.apply_refund(p, args.get("leg_id", ""))
                _confirm(record, p)
                return {"ok": True, "confirmation": record["message"]}, "traveler.refunded"
    except HTTPException as exc:
        return {"ok": False, "error": exc.detail}, None
    except Exception as exc:  # noqa: BLE001
        log.exception("voice tool failed")
        return {"ok": False, "error": str(exc)}, None
    return {"ok": False, "error": f"unknown tool {name}"}, None


# ---- session -----------------------------------------------------------------

async def _send(ws: WebSocket, payload: dict) -> None:
    with contextlib.suppress(Exception):
        await ws.send_json(payload)


async def run_session(ws: WebSocket, pnr: str, last_name: str, lang: str) -> None:
    await ws.accept()
    if lang not in LANGUAGES:
        lang = "en"
    try:
        with store.lock:
            p = traveler.find_passenger(pnr, last_name)
            instructions = build_instructions(p, lang)
            greeting = _greeting_instruction(p, lang)
    except HTTPException as exc:
        await _send(ws, {"type": "error", "message": exc.detail})
        await ws.close(code=4404)
        return
    if not (settings.voice_endpoint and settings.voice_api_key):
        await _send(ws, {"type": "error", "message": "Voice service is not configured on the server."})
        await ws.close(code=4503)
        return

    cfg = LANGUAGES[lang]
    await _send(ws, {"type": "state", "state": "connecting"})
    try:
        async with connect(
            endpoint=_resource_endpoint(),
            credential=AzureKeyCredential(settings.voice_api_key),
            model=settings.voice_model,
            api_version=settings.voice_api_version,
        ) as conn:
            session = RequestSession(
                modalities=[Modality.TEXT, Modality.AUDIO],
                instructions=instructions,
                voice=AzureStandardVoice(name=cfg["voice"], locale=cfg["locale"]),
                input_audio_format=InputAudioFormat.PCM16,
                output_audio_format=OutputAudioFormat.PCM16,
                input_audio_transcription=AudioInputTranscriptionOptions(model="azure-speech", language=cfg["stt"]),
                turn_detection=ServerVad(threshold=0.5, prefix_padding_ms=300, silence_duration_ms=600),
                tools=TOOLS,
                tool_choice="auto",
            )
            if settings.voice_audio_processing:
                session.input_audio_echo_cancellation = AudioEchoCancellation()
                session.input_audio_noise_reduction = AudioNoiseReduction(type="azure_deep_noise_suppression")
            await conn.session.update(session=session)

            state = {"responding": False, "greeted": False}

            async def from_browser() -> None:
                while True:
                    msg = await ws.receive()
                    if msg["type"] == "websocket.disconnect":
                        return
                    if msg.get("bytes") is not None:
                        await conn.input_audio_buffer.append(audio=base64.b64encode(msg["bytes"]).decode("ascii"))
                    elif msg.get("text"):
                        try:
                            data = json.loads(msg["text"])
                        except ValueError:
                            continue
                        if data.get("type") == "interrupt" and state["responding"]:
                            with contextlib.suppress(Exception):
                                await conn.response.cancel()
                        elif data.get("type") == "text" and str(data.get("text", "")).strip():
                            text = str(data["text"]).strip()[:500]
                            await _send(ws, {"type": "transcript", "role": "user", "text": text, "final": True, "id": None})
                            await conn.conversation.item.create(
                                item=UserMessageItem(content=[InputTextContentPart(text=text)]))
                            await conn.response.create()
                        elif data.get("type") == "end":
                            return

            async def from_service() -> None:
                async for event in conn:
                    et = event.type
                    if et == ServerEventType.SESSION_UPDATED:
                        await _send(ws, {"type": "ready"})
                        if not state["greeted"]:
                            state["greeted"] = True
                            await conn.response.create(additional_instructions=greeting)
                    elif et == ServerEventType.INPUT_AUDIO_BUFFER_SPEECH_STARTED:
                        await _send(ws, {"type": "speech_started", "interrupt": state["responding"]})
                        if state["responding"]:
                            with contextlib.suppress(Exception):
                                await conn.response.cancel()
                    elif et == ServerEventType.INPUT_AUDIO_BUFFER_SPEECH_STOPPED:
                        await _send(ws, {"type": "state", "state": "thinking"})
                    elif et == ServerEventType.CONVERSATION_ITEM_INPUT_AUDIO_TRANSCRIPTION_COMPLETED:
                        text = (getattr(event, "transcript", "") or "").strip()
                        if text:
                            await _send(ws, {"type": "transcript", "role": "user", "text": text, "final": True,
                                             "id": getattr(event, "item_id", None)})
                    elif et == ServerEventType.RESPONSE_CREATED:
                        state["responding"] = True
                        state["tool_pending"] = False
                        await _send(ws, {"type": "response_started"})
                    elif et == ServerEventType.RESPONSE_AUDIO_DELTA:
                        await _send(ws, {"type": "state", "state": "speaking"}) if not state.get("speaking") else None
                        state["speaking"] = True
                        await ws.send_bytes(event.delta)
                    elif et == ServerEventType.RESPONSE_AUDIO_TRANSCRIPT_DELTA:
                        await _send(ws, {"type": "transcript", "role": "assistant", "text": event.delta, "final": False,
                                         "id": getattr(event, "item_id", None)})
                    elif et == ServerEventType.RESPONSE_AUDIO_TRANSCRIPT_DONE:
                        await _send(ws, {"type": "transcript", "role": "assistant", "text": getattr(event, "transcript", ""),
                                         "final": True, "id": getattr(event, "item_id", None)})
                    elif et == ServerEventType.RESPONSE_AUDIO_DONE:
                        state["speaking"] = False
                    elif et == ServerEventType.RESPONSE_FUNCTION_CALL_ARGUMENTS_DONE:
                        try:
                            args = json.loads(event.arguments or "{}")
                        except ValueError:
                            args = {}
                        state["tool_pending"] = True
                        await _send(ws, {"type": "state", "state": "thinking"})
                        await _send(ws, {"type": "tool", "name": event.name, "args": args, "status": "running"})
                        result, publish = await asyncio.to_thread(_run_tool, p, event.name, args)
                        await _send(ws, {"type": "tool", "name": event.name, "args": args, "status": "done",
                                         "ok": result.get("ok", True)})
                        if publish and result.get("ok"):
                            bus.publish(publish, {"pnr": p["pnr"], "via": "voice"})
                            await _send(ws, {"type": "booking_changed"})
                        await conn.conversation.item.create(
                            item=FunctionCallOutputItem(call_id=event.call_id, output=json.dumps(result)))
                        await conn.response.create()
                    elif et == ServerEventType.RESPONSE_DONE:
                        state["responding"] = False
                        state["speaking"] = False
                        if not state.get("tool_pending"):
                            await _send(ws, {"type": "state", "state": "listening"})
                    elif et == ServerEventType.ERROR:
                        message = getattr(event.error, "message", "") or "Voice service error"
                        if "no active response" in message.lower():
                            continue
                        log.warning("Voice Live error: %s", message)
                        await _send(ws, {"type": "error", "message": message})

            tasks = [asyncio.create_task(from_browser()), asyncio.create_task(from_service())]
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for t in pending:
                t.cancel()
            for t in done:
                exc = t.exception()
                if exc and not isinstance(exc, (WebSocketDisconnect, asyncio.CancelledError)):
                    raise exc
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001
        log.exception("voice session failed")
        await _send(ws, {"type": "error", "message": f"Could not reach the voice service: {exc}"})
    finally:
        with contextlib.suppress(Exception):
            await ws.close()
