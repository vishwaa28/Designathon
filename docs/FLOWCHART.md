# ARRO – Flow Charts

## 1. End-to-end incident lifecycle

```mermaid
flowchart TD
    A([Feed event<br/>weather · asset health · status]) --> B{Thresholds<br/>breached?}
    B -- No --> Z1([No action · logged])
    B -- Yes --> C[Classify severity<br/>scope + disruption window<br/>situation report]
    C --> D1[Impact analysis<br/>rotation propagation<br/>crew duty limits<br/>missed connections<br/>priority passengers]
    C --> D2[Infrastructure triage<br/>root-cause ranking<br/>team dispatch + work order<br/>repair window P50 / P90]
    D1 --> E[Recovery planner<br/>3 strategies per disruption type<br/>seat-inventory re-accommodation<br/>crew reserves · cost model]
    D2 --> E
    E --> F[Trade-off analyst<br/>multi-criteria score<br/>confidence from repair uncertainty<br/>P90 sensitivity · rationale]
    F --> G{{Controller approval<br/>workflow paused}}
    G -- Approve / override --> H[Execute plan<br/>retime · cancel · divert<br/>move passengers]
    G -- Re-plan with new priority --> E
    G -- Field update: repair window changed --> D1 & D2
    G -- Field update: crew or seats changed --> E
    G -- Reject --> Z2([Closed · manual handling])
    H --> I[Personalised notifications<br/>language · channel · self-service link<br/>assisted calls for WCHR / UMNR / MEDA]
    I --> J([Resolved])
    I -.-> K[Traveler self-service<br/>rebook or refund]
    D2 -.-> L[Work order lifecycle<br/>Dispatched → On site → In progress → Completed]
    L -.->|Completed| M([Asset restored])
```

## 2. LangGraph agent graph

This is the exact graph compiled in `server/app/agents/graph.py` and rendered live on the **Agent orchestration** page.

```mermaid
flowchart LR
    S((START)) --> DET[Disruption Detection]
    DET -- Disruption --> IMP[Impact Analysis]
    DET -- Disruption --> INF[Infrastructure Triage]
    DET -- No disruption --> E((END))
    IMP --> REC[Recovery Planner]
    INF --> REC
    REC --> TRD[Trade-off Analyst]
    TRD --> APP{{Controller Approval<br/>interrupt}}
    APP -- Approved --> NOT[Traveler Notification]
    APP -- Re-plan --> REC
    APP -- New information --> IMP
    APP -- New information --> INF
    APP -- Rejected --> E
    NOT --> E
```

| Edge type | Mechanism |
|---|---|
| Parallel fan-out after detection | Conditional edge returning `["impact_analysis", "infra_triage"]`; LangGraph runs both in the same super-step and joins at `recovery_planner` |
| Human-in-the-loop | `interrupt()` inside `controller_approval`; resumed by `Command(resume=decision)` from `POST /incidents/{id}/decision` or `/updates` |
| Re-plan and re-assess loops | `Command(goto=...)` from `controller_approval`, declared with `destinations=` so the loops appear in the exported graph |

## 3. Controller approval decision flow

```mermaid
flowchart TD
    A[Options + recommendation ready] --> B[Status: AWAITING_APPROVAL<br/>graph interrupted]
    B --> C{Controller action}
    C -->|Approve recommended| D[Record decision]
    C -->|Approve other option| O{Override reason<br/>provided?}
    O -- No --> C
    O -- Yes --> D
    D --> E[Status: EXECUTING → notification agent]
    C -->|Re-plan| P[Choose priority:<br/>balanced · passenger · cost · speed<br/>max delay · avoid cancellations]
    P --> Q[plan_version + 1<br/>Status: REPLANNING] --> R[Recovery planner] --> A
    C -->|Inject field update| U{Update type}
    U -->|Restoration delayed +90 min<br/>Early restoration −45 min| V[Shift repair window<br/>re-run impact + triage] --> R
    U -->|Reserve crew unavailable<br/>Seat inventory −50 %| W[Adjust constraints] --> R
    C -->|Reject| X[Status: REJECTED · END]
```

## 4. Recovery option generation and scoring

```mermaid
flowchart TD
    A[Scope type] --> B{Disruption}
    B -->|Airport closure – weather| W1[A · Hold and retime]
    B -->|Airport closure – weather| W2[B · Cancel and consolidate]
    B -->|Airport closure – weather| W3[C · Divert + switch mode]
    B -->|Rail corridor block| R1[A · Caution order<br/>FAIL if flooding]
    B -->|Rail corridor block| R2[B · Hold at stations]
    B -->|Rail corridor block| R3[C · Short-terminate + coach bridge]
    B -->|Aircraft on ground| G1[A · Tail swap with spare]
    B -->|Aircraft on ground| G2[B · Delay until repaired]
    B -->|Aircraft on ground| G3[C · Cancel and re-accommodate]
    W1 & W2 & W3 & R1 & R2 & R3 & G1 & G2 & G3 --> E[evaluate_plan]
    E --> E1[Propagate delays through rotations]
    E1 --> E2[Crew duty check → assign reserves]
    E2 --> E3[Re-accommodate passengers<br/>priority first · min connection times<br/>same mode, then alternate mode]
    E3 --> E4[Cost: delay minutes · care · hotel<br/>cancellation compensation · rebooking<br/>alternate mode · coaches · reserve crew · diversion]
    E4 --> E5[Constraint checks PASS / WARN / FAIL]
    E5 --> S[Score = 100 − 45·weighted_norm − 12·FAIL − 3·WARN]
    S --> CF[Confidence = data quality<br/>− repair uncertainty share<br/>− constraint penalties]
    CF --> SEN[P90 sensitivity: re-run with P90 repair]
    SEN --> REC[Recommend best feasible option]
```

## 5. Traveler notification and self-service flow

```mermaid
sequenceDiagram
    autonumber
    participant N as Notification agent
    participant L as Language model
    participant S as Store
    participant T as Traveler
    participant P as Self-service portal

    N->>S: Apply approved plan (retime, cancel, divert, move pax)
    N->>L: Templates per outcome type × top languages
    L-->>N: JSON templates (fallback to built-in EN / HI)
    loop Every affected passenger
        N->>N: Render in passenger language, add self-service link
        N->>N: Assisted-call flag for WCHR / UMNR / MEDA
        N->>S: Notification (APP · SMS · WhatsApp · Email)
    end
    T->>P: Open link (PNR + last name prefilled)
    P->>S: GET /traveler/{pnr}
    alt Wants a different option
        P->>S: GET /traveler/{pnr}/alternatives
        T->>P: Select service
        P->>S: POST /traveler/{pnr}/rebook
        S-->>T: Rebooking confirmed
    else Prefers refund
        P->>S: POST /traveler/{pnr}/refund
        S-->>T: Refund initiated
    end
```

## 6. Incident status state machine

```mermaid
stateDiagram-v2
    [*] --> DETECTING
    DETECTING --> NO_ACTION: below thresholds
    DETECTING --> ANALYZING: disruption confirmed
    ANALYZING --> PLANNING
    PLANNING --> AWAITING_APPROVAL
    AWAITING_APPROVAL --> REPLANNING: re-plan / field update
    REPLANNING --> ANALYZING: repair window changed
    REPLANNING --> PLANNING: priorities / constraints changed
    AWAITING_APPROVAL --> EXECUTING: approved
    AWAITING_APPROVAL --> REJECTED: rejected
    EXECUTING --> RESOLVED: plan applied, travelers notified
    NO_ACTION --> [*]
    REJECTED --> [*]
    RESOLVED --> [*]
```
