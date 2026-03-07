"""Repository interfaces. Implementations are swappable (SQLite, in-memory, etc.)."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from app.models.domain import Goal, Message, Thread
from app.models.domain import CoachPhase


class IThreadRepository(ABC):
    """Abstract interface for thread persistence."""

    @abstractmethod
    def get(self, thread_id: str) -> Optional[Thread]:
        """Get a thread by ID."""
        pass

    @abstractmethod
    def get_by_patient(self, patient_id: str) -> Optional[Thread]:
        """Get the active thread for a patient (if any)."""
        pass

    @abstractmethod
    def save(self, thread: Thread) -> Thread:
        """Create or update a thread."""
        pass

    @abstractmethod
    def add_message(self, thread_id: str, message: Message) -> None:
        """Append a message to a thread."""
        pass

    @abstractmethod
    def update_phase(self, thread_id: str, phase: CoachPhase) -> None:
        """Update the phase of a thread."""
        pass

    @abstractmethod
    def update_goal(self, thread_id: str, goal: Goal) -> None:
        """Set the goal for a thread."""
        pass

    @abstractmethod
    def update_unanswered_count(self, thread_id: str, count: int) -> None:
        """Update unanswered message count."""
        pass

    @abstractmethod
    def update_goal_confirmed_at(self, thread_id: str, dt: datetime) -> None:
        """Set when the goal was first confirmed (for Day 2/5/7 scheduling)."""
        pass

    @abstractmethod
    def update_last_coach_message_at(self, thread_id: str, dt: datetime) -> None:
        """Set when the coach last sent a message (for disengagement backoff)."""
        pass

    @abstractmethod
    def update_checkins_sent(self, thread_id: str, sent: list[int]) -> None:
        """Update which scheduled check-in days have been sent (e.g. [2, 5, 7])."""
        pass

    @abstractmethod
    def list_threads_by_phases(self, phases: list[CoachPhase]) -> list[Thread]:
        """List threads in the given phases (for scheduler)."""
        pass

    @abstractmethod
    def list_all(self) -> list[Thread]:
        """List all threads (for clinician dashboard)."""
        pass
