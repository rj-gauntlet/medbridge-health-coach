"""Tests for thread repositories."""

from datetime import datetime

import pytest

from app.models.domain import CoachPhase, Goal, Message, MessageRole, Thread
from app.repositories.in_memory import InMemoryThreadRepository
from app.repositories.sqlite_repo import SQLiteThreadRepository


class TestInMemoryThreadRepository:
    def test_save_and_get(self, in_memory_repo):
        thread = Thread(thread_id="t1", patient_id="p1", phase=CoachPhase.PENDING)
        in_memory_repo.save(thread)
        loaded = in_memory_repo.get("t1")
        assert loaded is not None
        assert loaded.thread_id == "t1"
        assert loaded.patient_id == "p1"
        assert loaded.phase == CoachPhase.PENDING

    def test_get_by_patient(self, in_memory_repo):
        thread = Thread(thread_id="t1", patient_id="p1", phase=CoachPhase.ACTIVE)
        in_memory_repo.save(thread)
        loaded = in_memory_repo.get_by_patient("p1")
        assert loaded is not None
        assert loaded.thread_id == "t1"

    def test_get_missing_returns_none(self, in_memory_repo):
        assert in_memory_repo.get("nonexistent") is None
        assert in_memory_repo.get_by_patient("nonexistent") is None

    def test_add_message(self, in_memory_repo):
        thread = Thread(thread_id="t1", patient_id="p1", phase=CoachPhase.ONBOARDING)
        in_memory_repo.save(thread)
        in_memory_repo.add_message("t1", Message(role=MessageRole.USER, content="Hi"))
        loaded = in_memory_repo.get("t1")
        assert len(loaded.messages) == 1
        assert loaded.messages[0].content == "Hi"
        assert loaded.messages[0].role == MessageRole.USER

    def test_update_phase(self, in_memory_repo):
        thread = Thread(thread_id="t1", patient_id="p1", phase=CoachPhase.PENDING)
        in_memory_repo.save(thread)
        in_memory_repo.update_phase("t1", CoachPhase.ACTIVE)
        loaded = in_memory_repo.get("t1")
        assert loaded.phase == CoachPhase.ACTIVE

    def test_update_goal(self, in_memory_repo):
        thread = Thread(thread_id="t1", patient_id="p1", phase=CoachPhase.ACTIVE)
        in_memory_repo.save(thread)
        goal = Goal(description="Exercise 3x/week", frequency="3 times")
        in_memory_repo.update_goal("t1", goal)
        loaded = in_memory_repo.get("t1")
        assert loaded.goal is not None
        assert loaded.goal.description == "Exercise 3x/week"

    def test_update_unanswered_count(self, in_memory_repo):
        thread = Thread(thread_id="t1", patient_id="p1", phase=CoachPhase.ACTIVE)
        in_memory_repo.save(thread)
        in_memory_repo.update_unanswered_count("t1", 2)
        loaded = in_memory_repo.get("t1")
        assert loaded.unanswered_count == 2

    def test_update_goal_confirmed_at(self, in_memory_repo):
        thread = Thread(thread_id="t1", patient_id="p1", phase=CoachPhase.ACTIVE)
        in_memory_repo.save(thread)
        now = datetime.utcnow()
        in_memory_repo.update_goal_confirmed_at("t1", now)
        loaded = in_memory_repo.get("t1")
        assert loaded.goal_confirmed_at is not None

    def test_update_checkins_sent(self, in_memory_repo):
        thread = Thread(thread_id="t1", patient_id="p1", phase=CoachPhase.ACTIVE)
        in_memory_repo.save(thread)
        in_memory_repo.update_checkins_sent("t1", [2, 5])
        loaded = in_memory_repo.get("t1")
        assert loaded.checkins_sent == [2, 5]

    def test_list_threads_by_phases(self, in_memory_repo):
        in_memory_repo.save(Thread(thread_id="t1", patient_id="p1", phase=CoachPhase.ACTIVE))
        in_memory_repo.save(Thread(thread_id="t2", patient_id="p2", phase=CoachPhase.DORMANT))
        in_memory_repo.save(Thread(thread_id="t3", patient_id="p3", phase=CoachPhase.ACTIVE))
        result = in_memory_repo.list_threads_by_phases([CoachPhase.ACTIVE])
        assert len(result) == 2
        ids = {t.thread_id for t in result}
        assert ids == {"t1", "t3"}


class TestSQLiteThreadRepository:
    def test_save_and_get(self, sqlite_repo):
        thread = Thread(thread_id="t1", patient_id="p1", phase=CoachPhase.PENDING)
        sqlite_repo.save(thread)
        loaded = sqlite_repo.get("t1")
        assert loaded is not None
        assert loaded.thread_id == "t1"
        assert loaded.patient_id == "p1"

    def test_add_message_persists(self, sqlite_repo):
        thread = Thread(thread_id="t1", patient_id="p1", phase=CoachPhase.ONBOARDING)
        sqlite_repo.save(thread)
        sqlite_repo.add_message("t1", Message(role=MessageRole.USER, content="Hello"))
        loaded = sqlite_repo.get("t1")
        assert len(loaded.messages) == 1
        assert loaded.messages[0].content == "Hello"

    def test_list_threads_by_phases(self, sqlite_repo):
        sqlite_repo.save(Thread(thread_id="t1", patient_id="p1", phase=CoachPhase.ACTIVE))
        sqlite_repo.save(Thread(thread_id="t2", patient_id="p2", phase=CoachPhase.DORMANT))
        result = sqlite_repo.list_threads_by_phases([CoachPhase.ACTIVE])
        assert len(result) == 1
        assert result[0].thread_id == "t1"
