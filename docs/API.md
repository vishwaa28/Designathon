# ARRO – API Reference

Base URL: `http://localhost:8000/api` (proxied as `/api` by the Vite dev server). Interactive OpenAPI docs: `http://localhost:8000/docs`.

## Platform

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness and active model provider |
| GET | `/settings/llm` | `{active, providers: [{id, label, model, configured}]}` |
| PUT | `/settings/llm` | Switch provider. Body `{"provider": "gemini" \| "azure"}`. 400 if the provider has no credentials |
| POST | `/simulation/reset` | Regenerate the operating day and clear incidents, work orders and notifications |
| GET | `/stream` | Server-sent events. Each message is `{id, type, ts, data}`; types: `agent.started`, `agent.completed`, `agent.failed`, `incident.created`, `incident.updated`, `approval.required`, `feed`, `feed.update`, `work_order.updated`, `notifications.sent`, `traveler.rebooked`, `traveler.refunded`, `settings.updated`, `simulation.reset` |

## Operations

| Method | Path | Description |
|---|---|---|
| GET | `/dashboard` | KPIs, hub status with weather, departures by hour, recent incidents, live feed |
| GET | `/trips` | Query: `mode` (`FLIGHT`/`TRAIN`), `status`, `q`, `disrupted`, `limit` |
| GET | `/trips/{trip_id}` | Trip with crew and duty status, vehicle rotation, passenger manifest |
| GET | `/assets` | Assets with live telemetry, plus maintenance teams |
| GET | `/work-orders` | Work orders, newest first |
| PATCH | `/work-orders/{wo_id}` | Body `{"status": "DISPATCHED" \| "ON_SITE" \| "IN_PROGRESS" \| "COMPLETED"}`. Completing restores the asset |

## Feeds and incidents

| Method | Path | Description |
|---|---|---|
| GET | `/feeds/scenarios` | Injectable scenarios and field-update types |
| GET | `/feeds/live` | Recent feed events (`limit` ≤ 150) |
| POST | `/feeds/trigger` | Body `{"scenario_id": "wx-maa-thunderstorm"}` → `201 {incident_id, …}`. Starts the agent graph |
| GET | `/incidents` | Incident summaries |
| GET | `/incidents/{id}` | Full incident: event, detection, impact, infra, options, recommendation, decision, notifications summary, trace, plan history, work order |
| POST | `/incidents/{id}/decision` | Controller decision (see below). `202`, `409` if not awaiting approval |
| POST | `/incidents/{id}/updates` | Body `{"update_type": "restoration_delayed" \| "early_restoration" \| "crew_shortage" \| "inventory_drop"}`. Re-assesses or re-plans |
| GET | `/incidents/{id}/notifications` | Query: `outcome`, `language`, `q`, `priority`, `limit` ≤ 500, `offset` |
| GET | `/agents/graph` | Compiled LangGraph nodes (with agent metadata) and edges |

### Decision body

```json
{
  "action": "approve",
  "option_id": "P1-C",
  "controller": "Duty controller",
  "notes": "",
  "override_reason": null,
  "preferences": null
}
```

- `approve` – `option_id` required; `override_reason` required by the UI when the option is not the recommendation.
- `reject` – closes the incident without executing.
- `replan` – `preferences: {"priority": "balanced" | "passenger" | "cost" | "speed", "max_delay_min": 15–1440, "avoid_cancellations": bool}`.

## E-mail and SMS delivery

Only the four contact travelers (`contact: true`) receive real messages; every other notification is a simulated record. Each delivered notification carries `deliveries: [{channel, to, status, provider, error}]` and `status` `SENT` / `PARTIAL` / `FAILED` / `NOT_CONFIGURED`.

| Method | Path | Description |
|---|---|---|
| GET | `/delivery/status` | `{email: {configured, provider, host, sender}, sms: {configured, provider}, contacts: [...]}` with masked e-mail and phone, current trip and last notification |
| POST | `/delivery/test` | Body `{"pnr": "VSHWA1" \| null, "channels": ["EMAIL", "SMS"]}`. `pnr` null sends to all four contacts |
| POST | `/notifications/{id}/resend` | Re-send one contact notification by e-mail and SMS |

## Voice assistant

| Method | Path | Description |
|---|---|---|
| GET | `/voice/status` | `{configured, model, languages: [{id, label, native}]}` |
| WS | `/voice/ws?pnr=&name=&lang=en\|ta\|te` | Real-time voice session for one booking |

**Client → server:** binary frames of 24 kHz mono PCM16 microphone audio (40 ms recommended); text frames `{"type":"text","text":"…"}` (typed message), `{"type":"interrupt"}`, `{"type":"end"}`.

**Server → client:** binary frames of 24 kHz mono PCM16 assistant speech; JSON frames:

| `type` | Payload |
|---|---|
| `state` | `state`: `connecting`, `listening`, `thinking`, `speaking` |
| `ready` | Session configured, microphone audio is now accepted |
| `speech_started` | Caller started speaking (`interrupt` is true if the assistant was talking: stop playback) |
| `response_started` | A new assistant turn begins |
| `transcript` | `role` (`user` / `assistant`), `text`, `final`, `id`; assistant text streams as deltas until `final` |
| `tool` | `name`, `args`, `status` (`running` / `done`), `ok` – booking status, alternatives, rebook or refund calls |
| `booking_changed` | The assistant rebooked or refunded; reload the booking |
| `error` | `message`; the socket closes afterwards |

## Traveler self-service

All endpoints require the passenger's `last_name` as verification.

| Method | Path | Description |
|---|---|---|
| GET | `/traveler/{pnr}?last_name=` | Passenger, itinerary legs, latest notifications, actionable legs |
| GET | `/traveler/{pnr}/alternatives?last_name=&leg_trip_id=` | Same-mode and alternate-mode services with open seats in the next 24 h |
| POST | `/traveler/{pnr}/rebook` | Body `{"last_name", "leg_trip_id", "new_trip_id"}` |
| POST | `/traveler/{pnr}/refund` | Body `{"last_name", "leg_trip_id"}` |
