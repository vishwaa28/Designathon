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

The four contact travelers (`contact: true`) are booked on every flight (one booking per flight, references derived from the base reference, e.g. `VSH101`). Real e-mail and SMS go out once per person per run, for the soonest affected flight; the other contact bookings get a record with `deliveries: []` that can be sent with `/notifications/{id}/resend`. `/delivery/status` lists the four people (primary bookings).

Only the four contact travelers (`contact: true`) receive real messages; every other notification is a simulated record. Each delivered notification carries `deliveries: [{channel, to, status, provider, error}]` and `status` `SENT` / `PARTIAL` / `FAILED` / `NOT_CONFIGURED`.

| Method | Path | Description |
|---|---|---|
| GET | `/delivery/status` | `{email: {configured, provider, host, sender}, sms: {configured, provider}, contacts: [...]}` with masked e-mail and phone, current trip and last notification |
| POST | `/delivery/test` | Body `{"pnr": "VSHWA1" \| null, "channels": ["EMAIL", "SMS"]}`. `pnr` null sends to all four contacts |
| POST | `/notifications/{id}/resend` | Re-send one contact notification by e-mail and SMS |

## Crowd monitor

Camera frames are counted by the active vision model (Azure Responses `input_image` or Gemini). Each count is stored in SQLite and the state served to the UI is a rolling median of the last 5 readings (180 s). No numbers are produced when the model is unavailable: the frame call returns `503`.

| Method | Path | Description |
|---|---|---|
| GET | `/crowd/overview` | `{terminals: [{id, name, capacity, total_people, queue_people, occupancy_pct, peak_density, peak_camera, level, max_wait_min, cameras_live, cameras_total, needs_action, cameras: [...], plan}], vision, frame_interval_s}`. Each camera has a `kind`: `security` (queue with lanes, adds `wait_min`), `concourse` (people walking to security) or `lounge` (seated hold area, adds `seats`). Density bands differ per kind |
| POST | `/crowd/cameras/{camera_id}/frame` | Body `{"image": "<base64 JPEG or data URL>"}` (≤ 1.5 MB). Counts people, stores the observation and returns the camera state. At most one analysis per camera every 5 s (`throttled: true` otherwise). Publishes `crowd.updated` |
| GET | `/crowd/terminals/{id}/plan` | Demand-driven rerouting plan. `inflow` is the expected arrivals at security in the next 15 min (from the concourse camera, else the departure schedule). `checkpoints` gives each checkpoint's `share_pct` of new arrivals, extra lanes and `wait_now_min` / `wait_after_min`; `outlook` compares the unguided and planned longest wait. `actions` are `DIRECT`, `OPEN_LANES`, `PRIORITY` and `CROWD_CONTROL`. `flights` carry the assigned `checkpoint`, `priority` (fast-track), `arrive_by`, `slack_min` / `slack_after_min` and `at_risk`. Also `recipients` and advisory history |
| POST | `/crowd/terminals/{id}/reroute` | Body `{"force": false}`. Sends the advisory (409 when crowd levels are normal and `force` is false). Real e-mail/SMS go only to the four contact travelers. Publishes `crowd.reroute` |

Formulas: density = people / area (m²), bands LOW < 0.75 ≤ MODERATE < 1.5 ≤ HIGH < 2.5 ≤ CRITICAL; wait = queue / (screening lanes × rate per lane); a flight is at risk when `minutes_to_departure − 35 − wait < 10`. Camera calibration (area, lanes, rates, video) lives in `server/app/data/reference.py`.

## Real-time flights (AviationStack)

| Method | Path | Description |
|---|---|---|
| GET | `/flights/status` | `{configured, provider, airport, cache_ttl_s, calls_today, calls_this_month}` |
| GET | `/flights/live?direction=departures\|arrivals&refresh=false` | Board for the airport: `{source: live\|cache\|stale-cache, error, fetched_at, age_s, count, by_status, terminals, items: [{flight, airline, status, terminal, gate, delay_min, scheduled, estimated, other: {iata, airport}, live}]}`. Cached in SQLite for 15 min; `refresh=true` is honoured at most once a minute. A failed refresh serves the last cached board |

## Passengers, contacts and database

| Method | Path | Description |
|---|---|---|
| GET | `/passengers?q=&contact=&limit=` | Passenger list; `contact: true` marks the four real contact travelers (masked e-mail and phone) |
| GET | `/contacts` | The contact travelers stored in SQLite |
| GET | `/delivery/log?limit=&pnr=` | Audit log of every e-mail/SMS attempt |
| GET | `/db/summary` | Row counts per SQLite table |

SQLite tables: `contacts`, `delivery_log`, `incident_log`, `crowd_observations`, `crowd_reroutes`, `flight_cache`, `api_usage`. The file is `server/data/arro.db` (override with `DATABASE_PATH`; `/tmp/arro.db` on Vercel, which is not persistent).

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
