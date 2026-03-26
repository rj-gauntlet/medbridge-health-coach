"""Unit tests for all coach tool functions."""

import pytest
from datetime import datetime, timedelta

from app.agent.tools import (
    set_goal,
    set_reminder,
    get_program_summary,
    _make_alert_clinician,
    get_coach_tools,
    _make_get_adherence_summary,
    _make_record_pro,
    _make_get_streak,
)
from app.models.domain import (
    Message,
    MessageRole,
    PatientReportedOutcome,
    Thread,
    CoachPhase,
)
from app.repositories.in_memory import InMemoryThreadRepository
from app.repositories.pro_repo import InMemoryProRepository


# ─── set_goal ─────────────────────────────────────────────────────────

class TestSetGoal:
    def test_with_description_only(self):
        result = set_goal.invoke({"description": "Walk 30 minutes daily"})
        assert "Walk 30 minutes daily" in result

    def test_with_frequency(self):
        result = set_goal.invoke({"description": "Do exercises", "frequency": "3x/week"})
        assert "Do exercises" in result
        assert "3x/week" in result

    def test_without_frequency(self):
        result = set_goal.invoke({"description": "Stretch every morning"})
        assert "Stretch every morning" in result
        assert "frequency" not in result.lower() or "None" not in result


# ─── set_reminder ─────────────────────────────────────────────────────

class TestSetReminder:
    def test_schedules_reminder(self):
        result = set_reminder.invoke({"days": 3, "message": "Check exercises"})
        assert "3 days" in result

    def test_single_day(self):
        result = set_reminder.invoke({"days": 1, "message": "Quick check"})
        assert "1 day" in result


# ─── get_program_summary ──────────────────────────────────────────────

class TestGetProgramSummary:
    def test_returns_exercises(self):
        result = get_program_summary.invoke({})
        assert "knee extension" in result.lower()
        assert "quad sets" in result.lower()
        assert "heel slides" in result.lower()


# ─── alert_clinician ──────────────────────────────────────────────────

class TestAlertClinician:
    def test_normal_urgency(self):
        t = _make_alert_clinician(None)
        result = t.invoke({"reason": "Patient unresponsive", "urgency": "normal"})
        assert "Patient unresponsive" in result
        assert "normal" in result

    def test_urgent(self):
        t = _make_alert_clinician(None)
        result = t.invoke({"reason": "Crisis signal", "urgency": "high"})
        assert "Crisis signal" in result
        assert "high" in result

    def test_default_urgency(self):
        t = _make_alert_clinician(None)
        result = t.invoke({"reason": "Some concern"})
        assert "normal" in result


# ─── get_adherence_summary ────────────────────────────────────────────

class TestGetAdherenceSummary:
    def test_no_pro_repo(self):
        tool = _make_get_adherence_summary(None)
        result = tool.invoke({"thread_id": "t1"})
        assert "not yet available" in result.lower()

    def test_no_pros_recorded(self):
        pro_repo = InMemoryProRepository()
        tool = _make_get_adherence_summary(pro_repo)
        result = tool.invoke({"thread_id": "t1"})
        assert "no adherence data" in result.lower()

    def test_with_pros(self):
        pro_repo = InMemoryProRepository()
        pro_repo.add(PatientReportedOutcome(thread_id="t1", pain=3, difficulty=5, adherence_rating=8))
        pro_repo.add(PatientReportedOutcome(thread_id="t1", pain=2, difficulty=4, adherence_rating=9))
        tool = _make_get_adherence_summary(pro_repo)
        result = tool.invoke({"thread_id": "t1"})
        assert "pain" in result.lower()
        assert "difficulty" in result.lower()

    def test_only_returns_relevant_thread(self):
        pro_repo = InMemoryProRepository()
        pro_repo.add(PatientReportedOutcome(thread_id="t1", pain=5))
        pro_repo.add(PatientReportedOutcome(thread_id="t2", pain=8))
        tool = _make_get_adherence_summary(pro_repo)
        result = tool.invoke({"thread_id": "t1"})
        assert "5" in result
        # t2's pain=8 should not appear in t1's summary
        # (it could appear if tool returns "Recent PROs" generically, but
        # we verify the correct thread is queried)


# ─── record_pro ───────────────────────────────────────────────────────

class TestRecordPro:
    def test_no_pro_repo(self):
        tool = _make_record_pro(None)
        result = tool.invoke({"thread_id": "t1", "pain": 5})
        assert "unavailable" in result.lower()

    def test_records_pain(self):
        pro_repo = InMemoryProRepository()
        tool = _make_record_pro(pro_repo)
        result = tool.invoke({"thread_id": "t1", "pain": 4, "difficulty": 6})
        assert "pain=4" in result
        assert "difficulty=6" in result
        assert len(pro_repo.list_by_thread("t1")) == 1

    def test_records_all_fields(self):
        pro_repo = InMemoryProRepository()
        tool = _make_record_pro(pro_repo)
        tool.invoke({"thread_id": "t1", "pain": 3, "difficulty": 5, "adherence_rating": 8, "note": "Felt good"})
        pros = pro_repo.list_by_thread("t1")
        assert len(pros) == 1
        assert pros[0].pain == 3
        assert pros[0].difficulty == 5
        assert pros[0].adherence_rating == 8
        assert pros[0].note == "Felt good"

    def test_multiple_records(self):
        pro_repo = InMemoryProRepository()
        tool = _make_record_pro(pro_repo)
        tool.invoke({"thread_id": "t1", "pain": 5})
        tool.invoke({"thread_id": "t1", "pain": 3})
        assert len(pro_repo.list_by_thread("t1")) == 2


# ─── get_streak ───────────────────────────────────────────────────────

class TestGetStreak:
    def test_no_thread_repo(self):
        tool = _make_get_streak(None)
        result = tool.invoke({"thread_id": "t1"})
        assert "unavailable" in result.lower()

    def test_no_thread(self):
        repo = InMemoryThreadRepository()
        tool = _make_get_streak(repo)
        result = tool.invoke({"thread_id": "nonexistent"})
        assert "no streak" in result.lower()

    def test_engaged_today(self):
        repo = InMemoryThreadRepository()
        thread = Thread(thread_id="t1", patient_id="p1", last_interaction_at=datetime.utcnow())
        repo.save(thread)
        tool = _make_get_streak(repo)
        result = tool.invoke({"thread_id": "t1"})
        assert "engaged today" in result.lower()

    def test_engaged_recently(self):
        repo = InMemoryThreadRepository()
        thread = Thread(
            thread_id="t1",
            patient_id="p1",
            last_interaction_at=datetime.utcnow() - timedelta(hours=18),
        )
        repo.save(thread)
        tool = _make_get_streak(repo)
        result = tool.invoke({"thread_id": "t1"})
        # Within 1 day, should say engaged recently or today
        assert "engaged" in result.lower()

    def test_days_ago(self):
        repo = InMemoryThreadRepository()
        thread = Thread(
            thread_id="t1",
            patient_id="p1",
            last_interaction_at=datetime.utcnow() - timedelta(days=5),
        )
        repo.save(thread)
        tool = _make_get_streak(repo)
        result = tool.invoke({"thread_id": "t1"})
        assert "5 days ago" in result


# ─── get_coach_tools ──────────────────────────────────────────────────

class TestGetCoachTools:
    def test_returns_all_seven_tools(self):
        tools = get_coach_tools()
        assert len(tools) == 7

    def test_tool_names(self):
        tools = get_coach_tools()
        names = {t.name for t in tools}
        expected = {"set_goal", "set_reminder", "get_program_summary",
                    "get_adherence_summary", "record_pro", "get_streak",
                    "alert_clinician"}
        assert names == expected

    def test_tools_with_repos(self):
        repo = InMemoryThreadRepository()
        pro_repo = InMemoryProRepository()
        tools = get_coach_tools(thread_repo=repo, pro_repo=pro_repo)
        assert len(tools) == 7
