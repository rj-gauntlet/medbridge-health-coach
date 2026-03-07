"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.api.routes import chat, dashboard, epic
from app.api.deps import get_thread_repository, get_consent_service, get_coach_service, get_pro_repository
from app.config import get_settings
from app.scheduler.jobs import create_scheduler

# Frontend path: frontend/ is sibling of backend/
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"

_scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _scheduler
    settings = get_settings()
    day_seconds = settings.scheduler_day_seconds
    thread_repo = get_thread_repository()
    consent_service = get_consent_service()
    pro_repo = get_pro_repository()
    coach = get_coach_service(thread_repo=thread_repo, consent_service=consent_service, pro_repo=pro_repo)
    _scheduler = create_scheduler(coach, day_seconds=day_seconds, interval_seconds=60)
    _scheduler.start()
    yield
    if _scheduler:
        _scheduler.shutdown(wait=False)


app = FastAPI(
    title="MedBridge AI Health Coach",
    description="AI-powered accountability partner for home exercise programs",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(dashboard.router)
app.include_router(epic.router)


@app.get("/health")
def health():
    return {"status": "ok"}


# Serve frontend
if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR), name="assets")

    @app.get("/")
    def index():
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.get("/dashboard")
    def dashboard():
        return FileResponse(FRONTEND_DIR / "dashboard.html")

    @app.get("/exercises")
    def exercises():
        return FileResponse(FRONTEND_DIR / "exercises.html")
