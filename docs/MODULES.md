# ARRO – Module Descriptions

```
Designathon/
├── server/                 FastAPI + LangGraph backend
│   ├── app/
│   │   ├── main.py         App factory, lifespan, routers
│   │   ├── config.py       Settings from .env
│   │   ├── core/           LLM gateway, event bus, utilities
│   │   ├── data/           Reference data, seed generator, in-memory store
│   │   ├── domain/         Deterministic operations engine
│   │   ├── agents/         LangGraph nodes, state, graph
│   │   ├── services/       Orchestrator, feeds, weather
│   │   └── api/            REST + SSE endpoints
│   ├── tests/smoke_test.py End-to-end workflow check
│   └── requirements.txt
├── client/                 React + Vite frontend
│   └── src/
│       ├── App.jsx         Routes (lazy-loaded pages)
│       ├── lib/            API client, SSE provider, hooks, formatters
│       ├── components/     UI kit, shell, incident panels, flow canvas
│       └── pages/          Screens
└── docs/                   Architecture, flow charts, modules, API
```

---

## 1. Backend

### 1.1 `core/`

| Module | Responsibility |
|---|---|
| `llm.py` | `LLMGateway` – single entry point for language-model calls. Holds the active provider (`gemini` or `azure`), builds the Gemini client (`genai.Client(api_key=…)`) or the Azure Foundry client (`OpenAI(base_url=<endpoint>/openai/v1, api_key=…)` using the Responses API). `complete()` returns text plus an `LLMCall` audit record; `complete_json()` additionally extracts JSON robustly from fenced or prose responses. Never raises on provider errors – callers receive `ok=False` and fall back. |
| `events.py` | Thread-safe `EventBus` ring buffer (`publish`, `since(last_id)`). Feeds the SSE stream. |
| `utils.py` | Time helpers (IST-aware `now`, ISO formatting/parsing), haversine distance, rounding and clamping. |

### 1.2 `data/`

| Module | Responsibility |
|---|---|
| `reference.py` | Static network: 12 airports, 11 rail stations, 17 aircraft + 1 spare, 15 rail rakes, maintenance teams, infrastructure assets, reserve crew, city → language map, name pools. |
| `seed.py` | Deterministic generator (`random.seed(42)`) for the operating day: 70 flights in aircraft rotations, 30 trains in rake rotations, crew pairings with duty limits, ~19,900 passengers with single and connecting itineraries (air-air, air-rail, rail-air), loyalty tiers, special-service requests (WCHR, UMNR, MEDA, SRCT), language and channel preferences. |
| `store.py` | In-memory `Store` with a re-entrant lock. Indexes trips, rotations, pairings, passengers, PNRs, assets, teams, incidents, work orders and notifications. Derived views (`trip_status`, `est_dep/arr`, `spare_seats`, `trip_view`, `pax_view`, `crew_view`, `asset_view`) and passenger priority scoring. |

### 1.3 `domain/` – deterministic engine

| Module | Responsibility |
|---|---|
| `detection.py` | `assess(event)` evaluates feed readings against operating limits (wind gusts, visibility, lightning distance, precipitation, signal faults, water level, aircraft system faults). Produces triggers, severity, confidence and the disruption scope (`AIRPORT_CLOSURE`, `CORRIDOR_BLOCK`, `VEHICLE_GROUNDED`) with a time window. |
| `geo.py` | Cached segment distances and block times. |
| `network.py` | Network effects: primary delays per scope (departure-queue spacing at reopened airports, corridor block windows, grounded vehicle); `propagate()` pushes delay through each rotation absorbing turnaround slack; `crew_breaches()` checks duty-time limits and identifies swap trips and reserve bases; `pax_effects()` finds delayed passengers and missed connections using minimum connection times (air-air 60, air-rail 120, rail-air 150, rail-rail 30 min). |
| `recovery.py` | Strategy library (three per disruption type) and `evaluate_plan()`, which applies cancellations, diversions and delays, allocates reserve crew, re-accommodates passengers against live seat inventory (priority passengers first, same mode then alternate mode, coach bridges), computes the INR cost breakdown, constraint checks (PASS / WARN / FAIL) and concrete actions. `generate_options()` returns options `P{version}-A/B/C` with P90 sensitivity. |
| `scoring.py` | Multi-criteria scoring with weight sets per controller priority (balanced, passenger, cost, speed) across passenger impact, cost, operational risk and recovery time. Confidence derives from data quality, repair-window uncertainty (P90 − P50 relative to horizon) and constraint penalties. Picks the best feasible option and produces rule-based pros and cons. |
| `triage.py` | Fault models per asset class (signal, track circuit, runway, aircraft): ranked probable causes, nearest qualified team, P50 / P90 restoration window (hazard clearance, travel, diagnosis, repair, parts lead time), parts, safety notes and checklist. |
| `notifications.py` | Message templates (English and Hindi built in), disruption reasons per language, localised units, placeholder rendering, self-service portal links and the assisted-call line for special-service passengers. |

### 1.4 `agents/` – LangGraph workflow

| Module | Node | Responsibility |
|---|---|---|
| `state.py` | – | `RecoveryState` typed dict; `history` uses an additive reducer so parallel nodes can append. |
| `runtime.py` | – | `@agent_node` decorator: records execution traces (status, timings, summary, model calls, output, plan version), publishes `agent.*` events and updates the incident record. |
| `detection_agent.py` | `detection` | Runs `assess()`, asks the model for a situation report and watch items, routes to the parallel branch or ends. |
| `impact_agent.py` | `impact_analysis` | Computes propagated delays, crew breaches, missed connections and priority passengers; model writes the impact narrative. |
| `infra_agent.py` | `infra_triage` | Runs triage, raises or revises the work order (`WO-2041…`), model writes the work description. |
| `recovery_agent.py` | `recovery_planner` | Generates and evaluates recovery options for the current plan version, preferences and adjustments. |
| `tradeoff_agent.py` | `tradeoff_analyst` | Scores options, computes confidence, asks the model for the recommendation rationale and per-option trade-offs, appends plan history. |
| `approval.py` | `controller_approval` | Human-in-the-loop gate using `interrupt()`. Handles approve (with override reason), reject, re-plan (new priorities → `recovery_planner`) and field updates (restoration delayed / early → re-assess impact and triage; crew shortage / inventory drop → re-plan). |
| `notification_agent.py` | `traveler_notification` | Writes the approved plan into the schedule and bookings, generates multilingual templates via the model (validated, with fallback), renders per-passenger messages with channel routing and assisted-call escalation, marks the incident resolved. |
| `graph.py` | – | Builds and compiles the `StateGraph` with the `InMemorySaver` checkpointer, holds agent metadata (`AGENT_REGISTRY`) and exports the graph structure for the UI. |

### 1.5 `services/`

| Module | Responsibility |
|---|---|
| `orchestrator.py` | Creates incidents, runs graph invocations on a thread pool (one LangGraph thread per incident), resumes interrupted graphs with controller decisions and field updates, and waits until the graph is parked at the approval gate before reporting status. |
| `feeds.py` | Scenario catalogue (Delhi thunderstorm, Agra signal failure, Mumbai aircraft hydraulic fault, Mumbai–Pune track flooding), event builder that degrades the related asset, and the background telemetry loop publishing asset-health, operations and weather ticks. |
| `voice.py` | Traveler voice bridge to Azure Speech Voice Live (`azure-ai-voicelive`, API-key credential). Builds per-booking instructions (itinerary, delays, disruption) in the chosen language, configures neural voices (`en-IN-NeerjaNeural`, `ta-IN-PallaviNeural`, `te-IN-ShrutiNeural`), speech recognition (`azure-speech`, per-language locale), server VAD with echo cancellation and noise suppression, and four function tools (`get_booking_status`, `get_alternatives`, `rebook`, `request_refund`) that call the same logic as the portal. Relays audio and transcripts to the browser and handles barge-in. |
| `weather.py` | Pulls current conditions for six hubs from Open-Meteo; uses a simulated feed when the API is unreachable and never overwrites a scenario-injected severe weather state. |

### 1.6 `api/`

| Module | Endpoints |
|---|---|
| `operations.py` | Health, LLM settings, simulation reset, dashboard KPIs, trips list and detail, assets, work orders |
| `incidents.py` | Scenario catalogue, live feed, trigger, incident list and detail, decision, field update, notifications, agent graph |
| `traveler.py` | Booking lookup, alternatives, self-service rebook, refund (the logic is shared with the voice assistant tools) |
| `voice.py` | Voice assistant status and the `/voice/ws` WebSocket |
| `stream.py` | `GET /api/stream` server-sent events |
| `schemas.py` | Pydantic request models |

See [API.md](API.md) for the full reference.

---

## 2. Frontend

### 2.1 `lib/`

| Module | Responsibility |
|---|---|
| `api.js` | Fetch wrapper (`get/post/put/patch`) with JSON error handling. |
| `stream.jsx` | `StreamProvider` holding one `EventSource` to `/api/stream`; `useStream(handler)` subscribes components to live events; `useStreamStatus()` drives the connection indicator. |
| `useApi.js` | Data hook: fetches a resource, reloads on matching stream events (debounced) and optionally on an interval. |
| `useVoiceAgent.js` | Voice conversation hook: microphone capture through the `public/pcm-worklet.js` AudioWorklet (resampled to 24 kHz PCM16), WebSocket streaming, gap-free scheduled playback with barge-in, transcript and tool-call state, live input/output level for the visualiser. |
| `format.js` | Time, duration, currency (INR lakh / crore), number and percentage formatting. |
| `agents.js` | Display metadata (title, icon, colour) for each agent node and provider labels. |

### 2.2 `components/`

| Component | Responsibility |
|---|---|
| `ui.jsx` | Design-system primitives: Card, Badge, Button, Kpi, Tabs, Segmented, Progress, Modal, Drawer, Table, Field, status badges. |
| `AppShell.jsx` | Navy sidebar navigation with approval counter, top bar with model provider switch, clock and event injection. |
| `ProviderSwitch.jsx` | Gemini / Azure Foundry segmented switch; unconfigured providers are disabled. |
| `ScenarioLauncher.jsx` | Modal to inject a simulated feed event. |
| `LiveFeed.jsx` | Streaming list of feed events. |
| `incident/*` | Incident workspace panels: lifecycle stepper, detection (thresholds, situation report), impact (services, crew, connections, priority passengers), options (option cards, criteria matrix, approval bar, re-plan and field-update controls, plan history), infrastructure (work order, repair timeline), notifications (analytics and message log). |
| `traveler/VoiceAgent.jsx` | Voice assistant panel for the traveler portal: language selector (English, Tamil, Telugu), animated orb and waveform reacting to live audio levels, mute and end controls, conversation transcript with tool-call notices, suggested prompts and a typed-message fallback. |
| `flow/*` | React Flow node types (agent, human gate, terminal), node inspector, execution log. |

### 2.3 `pages/`

| Page | Route | Purpose |
|---|---|---|
| `Overview.jsx` | `/` | Network KPIs, hub status with weather, departures by hour, live feeds, recent incidents |
| `Incidents.jsx` | `/incidents` | Incident register |
| `IncidentDetail.jsx` | `/incidents/:id` | Incident workspace with tabs: overview, impact, recovery options + approval, infrastructure, traveler notifications, audit trail |
| `Orchestration.jsx` | `/orchestration/:id?` | Live LangGraph canvas (n8n-style) with executed-path highlighting, node inspector, model calls and execution log |
| `Schedule.jsx` | `/schedule` | Flights and trains with filters; drawer with crew duty, rotation and passenger manifest |
| `Assets.jsx` | `/assets` | Work orders with status progression and repair windows, maintenance teams, asset-health telemetry |
| `TravelerPortal.jsx` | `/traveler` | Public self-service: PNR lookup, voice assistant, disruption notice, itinerary, alternatives, rebook, refund, message history |
