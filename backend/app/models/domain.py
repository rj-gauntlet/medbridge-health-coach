"""Domain models: phase, thread, messages, goal."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class CoachPhase(str, Enum):
    """Application-controlled phase state. Transitions are deterministic."""

    PENDING = "PENDING"
    ONBOARDING = "ONBOARDING"
    ACTIVE = "ACTIVE"
    RE_ENGAGING = "RE_ENGAGING"
    DORMANT = "DORMANT"


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Message(BaseModel):
    """A single chat message."""

    role: MessageRole
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Goal(BaseModel):
    """Structured exercise goal extracted from patient response."""

    description: str
    frequency: Optional[str] = None  # e.g., "3 times per week"
    extracted_at: datetime = Field(default_factory=datetime.utcnow)


class Thread(BaseModel):
    """Coach thread for a patient. Holds phase, messages, goal, and metadata."""

    thread_id: str
    patient_id: str
    phase: CoachPhase = CoachPhase.PENDING
    messages: list[Message] = Field(default_factory=list)
    goal: Optional[Goal] = None
    unanswered_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_interaction_at: Optional[datetime] = None
    goal_confirmed_at: Optional[datetime] = None  # When patient first set goal (for Day 2/5/7)
    last_coach_message_at: Optional[datetime] = None  # For disengagement backoff
    checkins_sent: list[int] = Field(default_factory=list)  # e.g. [2, 5, 7] for sent days

    @property
    def last_message(self) -> Optional[Message]:
        return self.messages[-1] if self.messages else None


# Alias for LangGraph state compatibility
ThreadState = dict
