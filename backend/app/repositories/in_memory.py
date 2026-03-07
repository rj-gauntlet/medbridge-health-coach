"""In-memory repository implementations for testing."""

from copy import deepcopy
from datetime import datetime
from typing import Optional

from app.models.domain import CoachPhase, Goal, Message, Thread
from app.repositories.interfaces import IThreadRepository


class InMemoryThreadRepository(IThreadRepository):
    """In-memory implementation. Thread-safe for single-threaded tests."""

    def __init__(self) -> None:
        self._threads: dict[str, Thread] = {}

    def get(self, thread_id: str) -> Optional[Thread]:
        t = self._threads.get(thread_id)
        return deepcopy(t) if t else None

    def get_by_patient(self, patient_id: str) -> Optional[Thread]:
        for t in self._threads.values():
            if t.patient_id == patient_id:
                return deepcopy(t)
        return None

    def save(self, thread: Thread) -> Thread:
        self._threads[thread.thread_id] = deepcopy(thread)
        return self._threads[thread.thread_id]

    def add_message(self, thread_id: str, message: Message) -> None:
        t = self._threads.get(thread_id)
        if t:
            t.messages.append(message)

    def update_phase(self, thread_id: str, phase: CoachPhase) -> None:
        t = self._threads.get(thread_id)
        if t:
            t.phase = phase

    def update_goal(self, thread_id: str, goal: Goal) -> None:
        t = self._threads.get(thread_id)
        if t:
            t.goal = goal

    def update_unanswered_count(self, thread_id: str, count: int) -> None:
        t = self._threads.get(thread_id)
        if t:
            t.unanswered_count = count

    def update_goal_confirmed_at(self, thread_id: str, dt: datetime) -> None:
        t = self._threads.get(thread_id)
        if t:
            t.goal_confirmed_at = dt

    def update_last_coach_message_at(self, thread_id: str, dt: datetime) -> None:
        t = self._threads.get(thread_id)
        if t:
            t.last_coach_message_at = dt

    def update_checkins_sent(self, thread_id: str, sent: list[int]) -> None:
        t = self._threads.get(thread_id)
        if t:
            t.checkins_sent = list(sent)

    def list_threads_by_phases(self, phases: list[CoachPhase]) -> list[Thread]:
        return [deepcopy(t) for t in self._threads.values() if t.phase in phases]

    def list_all(self) -> list[Thread]:
        def _sort_key(t: Thread):
            return (t.last_interaction_at or t.created_at)
        return [deepcopy(t) for t in sorted(self._threads.values(), key=_sort_key, reverse=True)]
