# AI Health Coach — Project Plan

This document captures deliverables, phased priorities, schedule, and success criteria for the MedBridge AI Health Coach hiring project.

---

## Timeline

| Milestone | Target |
|-----------|--------|
| **Current** | End of Week 3 |
| **Interview access** | Beginning of Week 6 |
| **Presentation** | Middle of Week 6 |
| **Coding target** | Complete in ~1 week |
| **Effort budget** | ~50 hours |

---

## Deliverables

| Deliverable | Purpose | Status |
|-------------|---------|--------|
| **GitHub repository** | Codebase with clean structure | Planned |
| **README.md** | Setup, run instructions, overview | Done |
| **Architecture doc** | High-level design, components, data flow | Done |
| **Project plan** | Deliverables, phases, schedule | Done |
| **Working web UI** | Primary demo artifact; intuitive UX | Planned |
| **API documentation** | OpenAPI/Swagger or equivalent | Planned |
| **Environment config** | `.env.example`, no secrets in repo | Planned |
| **Tests** | Repositories, consent gate, phase transitions, tools | Planned |
| **Docker Compose** | One-command local run (optional) | Nice-to-have |
| **Video walkthrough** | Submission aid (optional) | Nice-to-have |

---

## Phased Priorities

### Phase 1 — Core Agent & Flow (Days 1–2)

1. LangGraph phase router (PENDING → ONBOARDING → ACTIVE → RE_ENGAGING → DORMANT)
2. Onboarding subgraph and conversation flow (welcome, goal extraction, confirmation, storage)
3. Tool definitions + stubbed implementations (`set_goal`, `set_reminder`, `get_program_summary`, `get_adherence_summary`, `alert_clinician`)
4. Repository pattern + SQLite persistence
5. FastAPI endpoints: receive message, return coach response
6. Basic web UI (simple chat)

**Exit criteria:** User can chat with the coach through onboarding and get a stored goal.

---

### Phase 2 — Safety & Consent (Day 3)

7. Consent gate: mock `IConsentService`, checked on every request
8. Safety classifier: pre-delivery check for clinical content and crisis signals
9. Clinical redirect + crisis alert handling
10. Retry once with augmented prompt; safe fallback message

**Exit criteria:** Non-consented users blocked; clinical/crisis content handled safely.

---

### Phase 3 — Scheduling & Lifecycle (Day 4)

11. Scheduled follow-ups at Day 2, 5, 7 with tone adaptation (celebration, nudge, check-in)
12. Disengagement handling: exponential backoff (1→2→3), clinician alert at 3, transition to DORMANT
13. Warm re-engagement flow when dormant patient returns

**Exit criteria:** Time-based check-ins run; disengagement and re-engagement work end-to-end.

---

### Phase 4 — Polish & Documentation (Days 5–7)

14. README run instructions, architecture doc finalization
15. API docs, `.env.example`, tests
16. UX polish, presentation prep

**Exit criteria:** Demo-ready; docs and tests in place.

---

## Must-Have vs. Nice-to-Have

| Requirement | Must-Have | Nice-to-Have |
|-------------|-----------|--------------|
| Onboarding flow | ✓ | |
| LangGraph phase routing | ✓ | |
| Safety classifier + clinical boundaries | ✓ | |
| Consent gate | ✓ | |
| Tool calling (interface + invocation) | ✓ | |
| Scheduled follow-up (Day 2, 5, 7) | ✓ | |
| Disengagement (backoff, alert, re-engagement) | ✓ | |
| Edge cases in onboarding (no response, unrealistic, refusal, clinical Qs) | Partial | Full coverage |
| Docker Compose | | ✓ |
| Video walkthrough | | ✓ |

---

## Day-by-Day Schedule

| Day | Focus |
|-----|--------|
| **1** | Phase 1: Project setup, repositories, LangGraph skeleton, onboarding flow |
| **2** | Phase 1: Tool calling, FastAPI endpoints, basic web UI |
| **3** | Phase 2: Consent gate, safety classifier, redirects and alerts |
| **4** | Phase 3: Scheduled follow-ups, disengagement logic |
| **5** | Phase 4: Documentation, tests, UX polish |
| **6–7** | Buffer, demo rehearsal, presentation prep |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| LangGraph learning curve | Use official docs; agent framework chosen for spec fit |
| LLM cost overruns | GPT-4o-mini; limit test runs; optional usage caps |
| Scope creep | Stick to phased plan; defer edge cases to "full coverage" |
| Presentation timing | Demo script; one-click run; fallback screenshots/video |
