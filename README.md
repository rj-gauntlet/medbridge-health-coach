# MedBridge AI Health Coach

An AI-powered accountability partner that helps patients adhere to home exercise programs (HEPs) through onboarding, goal-setting, and proactive follow-up—without providing clinical advice.

## Overview

Healthcare providers prescribe home exercise programs to patients, but adherence is notoriously low. Clinicians are stretched thin and lack bandwidth for regular check-ins. This system provides an AI coach that:

- Guides patients through onboarding and goal-setting
- Performs scheduled follow-ups (Day 2, 5, 7)
- Handles disengagement with exponential backoff and clinician alerts
- Enforces safety boundaries (clinical content redirect, crisis detection)
- Operates only when patients have consented via MedBridge Go

## Tech Stack

| Layer | Technology |
|-------|------------|
| API | FastAPI |
| Agent | LangGraph + LangChain |
| LLM | OpenAI GPT-4o-mini |
| Storage | SQLite (repository pattern) |
| Scheduler | APScheduler |
| Frontend | Web UI (TBD) |

## Quick Start

```bash
# Create virtual environment and install
cd medbridge
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate   # macOS/Linux

pip install -r requirements.txt

# Configure
cp .env.example .env
# Add your OPENAI_API_KEY to .env

# Run backend (from medbridge/backend)
cd backend
uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000 (or your port) in your browser.

**Demo mode** (1 minute = 1 day for scheduling): Add `SCHEDULER_DAY_SECONDS=60` to `.env` to test Day 2/5/7 check-ins and disengagement without waiting real days.

## Tests

```bash
cd backend
..\.venv\Scripts\python.exe -m pytest
```

## API Docs

When the server is running:
- **Swagger UI**: http://127.0.0.1:8080/docs
- **ReDoc**: http://127.0.0.1:8080/redoc

## LLM Selection

### Primary: OpenAI GPT-4o-mini

We use **OpenAI GPT-4o-mini** as the primary model for the AI Health Coach. This choice prioritizes:

- **Cost efficiency** for development and iteration (~$0.15/1M input tokens, ~$0.60/1M output)
- **Strong tool/function calling** for `set_goal`, `set_reminder`, `get_program_summary`, `get_adherence_summary`, and `alert_clinician`
- **Low latency** for conversational flows
- **Broad adoption** and example coverage for agent workflows

### When to Consider Upgrading

**Transition to GPT-4o or Claude 3.5 Sonnet** when:

- **Safety classifier accuracy is insufficient** — Clinical boundary and mental health detection need higher precision in production
- **Goal extraction is inconsistent** — Patients use ambiguous or complex language; structured goal extraction degrades
- **Regulatory or compliance review** — A documented "best-effort" clinical boundary model is required
- **Higher reasoning over multi-turn flows** — Edge cases (refusals, unrealistic goals, clinical questions mid-flow) are not handled reliably

**Migration path:** The LLM client is abstracted behind an interface/config. Switching models requires updating configuration and prompts; no architectural changes are required.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — High-level design, components, data flow, state model
- [Project Plan](docs/PROJECT_PLAN.md) — Deliverables, phased priorities, schedule
- [API Reference](docs/API.md) — REST API endpoints

**Interactive API docs** (when server is running): http://127.0.0.1:8080/docs

## License

Proprietary — MedBridge hiring project.
