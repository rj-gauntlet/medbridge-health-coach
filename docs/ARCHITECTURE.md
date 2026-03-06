# AI Health Coach — Architecture

This document describes the high-level architecture, components, state model, and data flows for the MedBridge AI Health Coach.

---

## 1. System Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              AI HEALTH COACH SYSTEM                             │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────────────────────────────┐│
│  │   Web UI    │────▶│  FastAPI    │────▶│  Coach Service (Orchestrator)      ││
│  │  (Frontend) │     │  REST API   │     │  • Consent gate (every request)     ││
│  └─────────────┘     └─────────────┘     │  • LangGraph invocation             ││
│         ▲                    │           │  • Safety classifier (pre-send)     ││
│         │                    │           └──────────────────┬──────────────────┘│
│         │                    │                              │                   │
│         │                    │           ┌──────────────────▼──────────────────┐│
│         │                    │           │  LangGraph Agent                    ││
│         │                    │           │  • Main router (phase → subgraph)   ││
│         │                    │           │  • Onboarding subgraph              ││
│         │                    │           │  • Active subgraph                  ││
│         │                    │           │  • Re-engaging subgraph             ││
│         │                    │           │  • Tool bindings                    ││
│         │                    │           └──────────────────┬──────────────────┘│
│         │                    │                              │                   │
│         │                    ▼                              ▼                   │
│         │           ┌─────────────────────────────────────────────────────┐     │
│         │           │  Infrastructure Layer                               │     │
│         │           │  • Repositories (Patient, Conversation, Goal, etc.) │     │
│         │           │  • Mock MedBridge (Consent, Patient/Program data)   │     │
│         │           │  • Scheduler (APScheduler: Day 2/5/7, backoff)      │     │
│         │           └─────────────────────────────────────────────────────┘     │
│         │                              │                                        │
│         │                              ▼                                        │
│         │           ┌─────────────────────────────────────────────────────┐     │
│         └───────────│  SQLite (primary) / In-memory (tests)               │     │
│                     └─────────────────────────────────────────────────────┘     │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Component Breakdown

| Component | Responsibility | Notes |
|-----------|----------------|-------|
| **Web UI** | Chat interface, session handling, intuitive UX | SPA (React/Vue) or server-rendered templates |
| **FastAPI** | REST endpoints, request routing | `/api/chat`, `/api/sessions`, etc. |
| **Coach Service** | Orchestrator: consent check → LangGraph → safety check | Single entry point for all coach interactions |
| **LangGraph Main Router** | Reads phase state, dispatches to phase-specific subgraph | Phase transitions are deterministic (application code) |
| **Phase Subgraphs** | Onboarding, Active, Re-engaging flows | One subgraph per phase; each has distinct prompts and logic |
| **Tools** | `set_goal`, `set_reminder`, `get_program_summary`, `get_adherence_summary`, `alert_clinician` | LangChain tool format; implementations can be stubbed |
| **Safety Classifier** | Pre-delivery check for clinical/crisis content | Returns (safe, reason); triggers redirect/alert if not safe |
| **Consent Service** | MedBridge Go login + consent verification (mocked) | `can_interact(patient_id)` checked on every request |
| **Repositories** | Persistence abstraction (Patient, Conversation, Goal, Thread) | Repository pattern; SQLite impl, in-memory for tests |
| **Scheduler** | Day 2/5/7 follow-ups, exponential backoff jobs | APScheduler |

---

## 3. State Model

### Phase State (Application-Controlled)

Phase transitions are **deterministic**—driven by application logic, not LLM output.

```
PENDING ──▶ ONBOARDING ──▶ ACTIVE ◀──▶ RE_ENGAGING
                │              │              │
                │              └──────────────┼──▶ DORMANT
                │                            │         │
                │                            │         └── (return) ──▶ RE_ENGAGING
                └── (abandon/fail) ──────────┴────────▶ DORMANT
```

| Phase | Description |
|-------|-------------|
| **PENDING** | Thread created, awaiting first interaction |
| **ONBOARDING** | Multi-turn onboarding flow (welcome, goal extraction, confirmation) |
| **ACTIVE** | Patient has committed to a goal; normal follow-ups and check-ins |
| **RE_ENGAGING** | Patient was dormant; warm re-engagement flow |
| **DORMANT** | Patient has not responded after backoff (1→2→3); clinician alerted |

### Conversation State (LangGraph Checkpoint)

- `phase`: PENDING | ONBOARDING | ACTIVE | RE_ENGAGING | DORMANT
- `messages`: List of chat messages
- `goal`: Extracted structured goal (or null)
- `unanswered_count`: 0–3 for disengagement backoff
- `last_interaction_at`, `created_at`
- `thread_id`, `patient_id`

---

## 4. Data Flows

### 4.1 Incoming Patient Message

```
1. Web UI sends message → FastAPI
2. Coach Service:
   a. Consent gate: IConsentService.can_interact(patient_id)?
      → No: return "Please log in and consent"
   b. Load/create thread state (phase, messages, goal, etc.)
   c. Invoke LangGraph with (state, new_message)
   d. LangGraph routes by phase → subgraph runs → tools called → LLM generates reply
   e. Safety check: SafetyClassifier.check(generated_message)
      → Clinical/crisis: redirect/alert, retry once, else safe fallback
   f. Persist messages, update phase if needed
   g. Return response to UI
3. Scheduler (separate): Day 2/5/7 jobs enqueue check-in events
   → Coach Service invokes with synthetic "scheduled_checkin" message
```

### 4.2 Scheduled Check-In (Day 2, 5, 7)

```
1. APScheduler triggers job for patient_id at Day N
2. Job calls Coach Service with synthetic event:
   - type: "scheduled_checkin"
   - day: 2 | 5 | 7
3. Coach Service:
   - Consent gate
   - Load state
   - Invoke LangGraph with check-in context (day, goal, tone: celebration|nudge|check-in)
   - Safety check
   - Persist, return (or queue for delivery)
```

### 4.3 Disengagement Handling

```
- On send: if no reply within window, Scheduler job runs
- Backoff: 1 → 2 → 3 unanswered
- At 3: alert_clinician tool called; transition to DORMANT
- On return: transition DORMANT → RE_ENGAGING; use warm re-engagement subgraph
```

---

## 5. Project Structure

```
medbridge/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app
│   │   ├── config.py               # Env, LLM config
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   ├── chat.py
│   │   │   │   └── sessions.py
│   │   │   └── deps.py             # DI, repo injection
│   │   ├── services/
│   │   │   ├── coach_service.py
│   │   │   ├── consent_service.py  # + mock
│   │   │   └── safety_classifier.py
│   │   ├── agent/
│   │   │   ├── graph.py            # LangGraph main router
│   │   │   ├── subgraphs/
│   │   │   │   ├── onboarding.py
│   │   │   │   ├── active.py
│   │   │   │   └── re_engaging.py
│   │   │   ├── tools/
│   │   │   │   ├── definitions.py
│   │   │   │   └── implementations.py
│   │   │   └── state.py
│   │   ├── repositories/
│   │   │   ├── interfaces.py
│   │   │   ├── sqlite/
│   │   │   └── in_memory/          # tests
│   │   ├── scheduler/
│   │   │   └── jobs.py
│   │   └── models/                 # Pydantic, domain
│   └── tests/
├── frontend/
│   └── (SPA or server templates)
├── docs/
│   ├── ARCHITECTURE.md
│   ├── PROJECT_PLAN.md
│   └── API.md
├── .env.example
├── README.md
└── requirements.txt
```

---

## 6. Design Decisions

### Repository Pattern

- All persistence goes through abstract interfaces (`IPatientRepository`, `IConversationRepository`, etc.)
- Implementations: SQLite (production), In-memory (tests)
- Enables swapping datastores and simplifies testing without touching domain logic

### Mock MedBridge Integration

- `IConsentService` and `IPatientService` (or equivalent) are abstract
- Mock implementations simulate: logged-in + consented, not logged in, consent revoked
- No real MedBridge API; interfaces designed for future integration

### Safety Classifier

- Runs on every generated message before delivery
- Clinical content → hard redirect to care team
- Mental health crisis → urgent clinician alert
- Blocked messages: retry once with augmented prompt, then safe generic fallback

### Phase Routing

- Phase state lives in application/DB, not LLM memory
- LangGraph reads phase and routes to the correct subgraph
- Transitions (e.g., ONBOARDING → ACTIVE when goal confirmed) are application logic
