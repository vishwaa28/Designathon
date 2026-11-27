# ARRO – System Architecture

ARRO (Asset Response & Recovery Orchestrator) detects disruptions across a combined airline and rail network, quantifies the cascading impact, generates and scores recovery plans, waits for a duty controller's decision and then executes the plan and notifies every affected traveler.

## 1. Technology stack

| Layer | Technology |
|---|---|
| Frontend | React 19, Vite 8, Tailwind CSS v4, React Router, React Flow (`@xyflow/react`), Recharts, Lucide icons |
| Backend API | Python 3.14, FastAPI, Uvicorn, Pydantic v2, Server-Sent Events |
| Agent orchestration | LangGraph `StateGraph` with `InMemorySaver` checkpointer, `interrupt()` / `Command` for human-in-the-loop |
| Language models | Switchable at runtime: Google Gemini (`google-genai`, API key) or Azure AI Foundry (OpenAI v1 Responses API, API key – no `DefaultAzureCredential`) |
| External data | Open-Meteo public weather API (simulated fallback when unreachable); simulated asset-health and operations telemetry |

## 2. System context

```mermaid
flowchart LR
    subgraph Users
        C[Duty controller]
        T[Traveler]
        M[Maintenance team]
    end

    subgraph ARRO
        UI[Operations console<br/>React SPA]
        TP[Traveler self-service portal<br/>React SPA route /traveler]
        API[FastAPI backend]
    end

    subgraph External
        WX[Open-Meteo weather API]
        LLM1[Google Gemini]
        LLM2[Azure AI Foundry]
    end

    C -->|monitor, approve, re-plan| UI
    T -->|PNR lookup, rebook, refund| TP
    M -->|work order status| UI
    UI <-->|REST + SSE| API
    TP <-->|REST| API
    API -->|every 10 min| WX
    API -->|situation reports, rationale, templates| LLM1
    API -->|situation reports, rationale, templates| LLM2
```

## 3. Logical architecture

```mermaid
flowchart TB
    subgraph Client["client/ (React)"]
        direction TB
        Pages["Pages<br/>Overview · Incidents · Incident workspace<br/>Agent orchestration · Schedule · Assets · Traveler portal"]
        Comp["Components<br/>UI kit · Incident panels · Flow canvas · Provider switch"]
        Lib["lib<br/>api client · useApi hook · SSE StreamProvider · formatters"]
        Pages --> Comp --> Lib
    end

    subgraph Server["server/app (FastAPI)"]
        direction TB
        subgraph APIL["api/ – HTTP layer"]
            OPS[operations.py]
            INC[incidents.py]
            TRV[traveler.py]
            SSE[stream.py]
        end
        subgraph SVC["services/"]
            ORC[orchestrator.py<br/>graph threads, resume]
            FEED[feeds.py<br/>scenarios + telemetry loop]
            WEA[weather.py]
        end
        subgraph AG["agents/ – LangGraph"]
            G[graph.py]
            N1[detection] --> N2[impact_analysis]
            N1 --> N3[infra_triage]
            N2 --> N4[recovery_planner]
            N3 --> N4
            N4 --> N5[tradeoff_analyst]
            N5 --> N6[controller_approval]
            N6 --> N7[traveler_notification]
        end
        subgraph DOM["domain/ – deterministic engine"]
            DET[detection] 
            NET[network<br/>propagation · crew · connections]
            REC[recovery<br/>strategies · inventory · cost]
            SCO[scoring<br/>multi-criteria · confidence]
            TRI[triage<br/>fault models · repair window]
            NTF[notifications<br/>templates · rendering]
        end
        subgraph CORE["core/ + data/"]
            LLM[llm.py<br/>Gemini / Azure gateway]
            BUS[events.py<br/>event bus]
            STORE[store.py<br/>in-memory state]
            SEED[seed.py + reference.py<br/>100 services, ~20k passengers]
        end
    end

    Lib -->|/api/*| APIL
    Lib -.->|/api/stream| SSE
    APIL --> SVC
    ORC --> G
    AG --> DOM
    AG --> LLM
    AG --> BUS
    DOM --> STORE
    FEED --> STORE
    FEED --> BUS
    WEA --> STORE
    SSE --> BUS
    STORE --> SEED
```

### Design principles

- **Deterministic core, language model at the edges.** All operational numbers (delays, crew legality, seat allocation, costs, scores, confidence) are computed by the `domain/` engine. The language model writes situation reports, impact narratives, work-order descriptions, trade-off rationale and multilingual message templates. Every model call has a deterministic fallback, so the workflow completes even if the model is unavailable, and the UI shows which provider produced each artefact.
- **Controller in the loop.** The graph pauses at `controller_approval` using LangGraph `interrupt()`. Nothing is written to the operational schedule or sent to travelers until the controller approves.
- **Dynamic re-planning.** From the approval gate the controller can re-plan with different priorities (loop back to `recovery_planner`) or inject new field information (loop back to `impact_analysis` + `infra_triage` or to `recovery_planner`). Each loop increments the plan version and is kept in the plan history.
- **Live by default.** Every agent start/finish, incident change, feed event and work-order change is published on the event bus and pushed to the browser over SSE, so all screens update without polling.

## 4. Runtime and concurrency

```mermaid
sequenceDiagram
    autonumber
    participant UI as Browser
    participant API as FastAPI (event loop)
    participant ORC as Orchestrator
    participant TP as Thread pool
    participant G as LangGraph
    participant BUS as Event bus
    participant LLM as Gemini / Azure

    UI->>API: POST /api/feeds/trigger
    API->>ORC: trigger_scenario()
    ORC->>TP: submit graph.invoke(event, thread_id=INC-xxxx)
    API-->>UI: 201 incident id
    TP->>G: detection
    G->>LLM: situation report
    G->>BUS: agent.started / agent.completed
    par Parallel fan-out
        G->>G: impact_analysis
    and
        G->>G: infra_triage
    end
    G->>G: recovery_planner → tradeoff_analyst
    G->>BUS: incident.updated (AWAITING_APPROVAL)
    G-->>TP: interrupt() – thread parked in checkpointer
    BUS-->>UI: SSE events (live canvas + panels)
    UI->>API: POST /api/incidents/{id}/decision
    API->>ORC: submit_decision()
    ORC->>TP: graph.invoke(Command(resume=decision))
    TP->>G: controller_approval → traveler_notification
    G->>BUS: notifications.sent, incident.updated (RESOLVED)
    BUS-->>UI: SSE events
```

- Graph runs execute on a `ThreadPoolExecutor` so long model calls never block the FastAPI event loop.
- Each incident is a LangGraph thread (`thread_id = incident id`); the `InMemorySaver` checkpointer stores state between the interrupt and the controller's decision.
- The in-memory `Store` is guarded by a re-entrant lock; the `EventBus` is a thread-safe ring buffer that the SSE endpoint tails.
- Background tasks started in the FastAPI lifespan: the telemetry loop (asset, operations and weather ticks every 6 s) and the weather refresh (every 10 min).

## 5. Language-model gateway

```mermaid
flowchart LR
    A[Agent node] -->|complete / complete_json| GW[LLMGateway]
    GW -->|active = gemini| GEM[google-genai Client<br/>api_key, timeout]
    GW -->|active = azure| AZ[OpenAI client<br/>base_url = Foundry /openai/v1<br/>api_key]
    GEM --> P[Robust JSON parse]
    AZ --> P
    P -->|ok| A
    GW -->|error / timeout / not configured| FB[LLMCall ok=false]
    FB --> R[Deterministic fallback in agent]
```

- The active provider is switched from the top bar (`PUT /api/settings/llm`); providers without credentials are disabled in the switch.
- Every call is recorded as an `LLMCall` (provider, model, latency, purpose, error) and attached to the agent execution so the Orchestration page can show it.

## 5a. Traveler voice assistant

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser (traveler portal)
    participant S as FastAPI /api/voice/ws
    participant V as Azure Speech Voice Live
    participant T as Self-service logic

    B->>S: WebSocket (PNR, last name, language)
    S->>S: Verify booking, build instructions from itinerary and disruption
    S->>V: Connect with API key, session.update (voice, STT locale, VAD, tools)
    V-->>S: session.updated
    S-->>B: ready
    S->>V: response.create (greeting)
    loop Conversation
        B->>S: PCM16 24 kHz microphone frames
        S->>V: input_audio_buffer.append
        V-->>S: speech started / stopped, transcript
        V-->>S: audio deltas + transcript deltas
        S-->>B: PCM16 audio + JSON events
        opt Tool call
            V-->>S: function call (alternatives, rebook, refund)
            S->>T: execute against the store
            S-->>B: tool status, booking_changed
            S->>V: function output, response.create
        end
    end
```

- The Azure key stays on the server; the browser only talks to the backend WebSocket.
- Speech recognition uses `azure-speech` with the selected locale (`en-IN`, `ta-IN`, `te-IN`) and speech output uses Azure neural voices for the same locales.
- Barge-in: when the caller starts speaking the server cancels the active response and the browser stops queued playback.
- Booking changes require verbal confirmation (enforced in the assistant instructions) and use the same functions as the portal buttons.
- The model is configurable (`AZURE_VOICELIVE_MODEL`); audio-native `gpt-realtime` is not available in every Azure region, so a text model with Voice Live speech services (default `gpt-4.1`) is used.

## 6. Data model (in-memory)

| Collection | Contents |
|---|---|
| `trips` | 70 flights + 30 trains with schedule, vehicle, rotation, crew pairing, delay / cancellation / diversion state |
| `rotations` | Ordered trip chain per aircraft tail / rail rake |
| `pairings`, `reserves` | Crew pairings with duty-time limits; reserve crew per base |
| `passengers`, `pax_by_trip`, `pnr_index` | ~19,900 passengers with multi-leg itineraries (air-air, air-rail, rail-air), tier, special-service requests, language and channel |
| `assets`, `teams` | Infrastructure assets with live telemetry and baseline; maintenance teams with skills and ETA |
| `incidents` | Incident record: event, detection, impact, infra, options, recommendation, decision, notifications, trace, plan history |
| `work_orders`, `notifications`, `feed` | Work orders with repair windows, traveler messages, live feed |

## 7. Deployment

```mermaid
flowchart LR
    B[Browser] -->|:5173| V[Vite dev server<br/>proxy /api → :8000]
    V --> U[Uvicorn :8000<br/>FastAPI app]
    U --> E[(.env<br/>LLM keys)]
```

For production, `npm run build` produces static assets in `client/dist` that can be served by any CDN or reverse proxy (Nginx, Azure Static Web Apps), with `/api` routed to Uvicorn workers behind the proxy. Persistent stores (PostgreSQL for operational data, Redis for the event bus, `langgraph-checkpoint-postgres` for graph state) are drop-in replacements for the in-memory components.
