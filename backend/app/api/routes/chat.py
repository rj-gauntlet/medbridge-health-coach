"""Chat API routes."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_coach_service, get_thread_repository
from app.repositories.interfaces import IThreadRepository
from app.services.coach_service import CoachService

router = APIRouter(prefix="/api", tags=["chat"])


class MessageItem(BaseModel):
    role: str
    content: str
    created_at: str | None = None  # ISO timestamp for display


class GoalItem(BaseModel):
    description: str
    frequency: str | None


class ThreadResponse(BaseModel):
    thread_id: str | None
    phase: str
    messages: list[MessageItem]
    goal: GoalItem | None = None
    personality: str | None = None
    streak_days: int | None = None


class ChatRequest(BaseModel):
    patient_id: str
    message: str
    thread_id: str | None = None
    personality: str | None = None  # "encouraging" | "direct" | "calm"


class ChatResponse(BaseModel):
    reply: str
    thread_id: str
    phase: str
    blocked: bool
    error: str | None


@router.get(
    "/thread",
    response_model=ThreadResponse,
    summary="Get conversation",
    description="Returns the full message history for a patient, including any scheduled check-ins added by the scheduler.",
)
def get_thread(
    patient_id: str,
    thread_id: str | None = None,
    repo: IThreadRepository = Depends(get_thread_repository),
) -> ThreadResponse:
    thread = None
    if thread_id:
        thread = repo.get(thread_id)
    if not thread and patient_id:
        thread = repo.get_by_patient(patient_id)
    if not thread:
        return ThreadResponse(thread_id=None, phase="PENDING", messages=[], goal=None, personality=None, streak_days=None)
    def _to_iso_utc(dt) -> str | None:
        """Serialize datetime as ISO with Z suffix so client parses as UTC and displays in local time."""
        if dt is None:
            return None
        s = dt.isoformat()
        if s and not (s.endswith("Z") or "+" in s):
            s += "Z"
        return s

    messages = [
        MessageItem(
            role=m.role.value,
            content=m.content,
            created_at=_to_iso_utc(getattr(m, "created_at", None)),
        )
        for m in thread.messages
    ]
    goal_item = None
    if thread.goal:
        goal_item = GoalItem(description=thread.goal.description, frequency=thread.goal.frequency)
    personality = getattr(thread, "personality", None) or "encouraging"
    from datetime import datetime
    streak = 0
    if thread.last_interaction_at:
        now = datetime.utcnow()
        delta = (now - thread.last_interaction_at).days
        streak = 1 if delta == 0 else 0
    return ThreadResponse(
        thread_id=thread.thread_id,
        phase=thread.phase.value,
        messages=messages,
        goal=goal_item,
        personality=personality,
        streak_days=streak if streak else None,
    )


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Send message",
    description="Send a message to the coach and receive a response. Creates a new thread if none exists.",
)
def chat(
    body: ChatRequest,
    coach: CoachService = Depends(get_coach_service),
) -> ChatResponse:
    result = coach.process_message(
        patient_id=body.patient_id,
        user_message=body.message,
        thread_id=body.thread_id,
        personality=body.personality,
    )
    return ChatResponse(
        reply=result["reply"],
        thread_id=result["thread_id"],
        phase=result["phase"],
        blocked=result["blocked"],
        error=result.get("error"),
    )
