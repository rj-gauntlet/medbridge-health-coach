"""Tests for scheduled check-ins (Day 2/5/7), disengagement backoff,
DORMANT transitions, clinician alerts, and conversation summarization."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.models.domain import CoachPhase, Goal, Message, MessageRole, Thread
from app.repositories.in_memory import InMemoryThreadRepository
from app.repositories.pro_repo import InMemoryProRepository
from app.scheduler.jobs import (
    DISENGAGEMENT_BACKOFF_DAYS,
    SCHEDULED_CHECKIN_DAYS,
    run_disengagement_checks,
    run_scheduled_checkins,
    run_conversation_summaries,
    create_scheduler,
)
from app.services.coach_service import CoachService
from app.services.consent_service import MockConsentService
from app.services.safety_classifier import SafetyClassifier


# ─── Helpers ──────────────────────────────────────────────────────────

DAY_SECONDS = 86400  # real day


def _make_coach(repo: InMemoryThreadRepository | None = None) -> tuple:
    """Build a CoachService with mocked graph."""
    from app.repositories.pro_repo import InMemoryAlertRepository
    repo = repo or InMemoryThreadRepository()
    pro_repo = InMemoryProRepository()
    alert_repo = InMemoryAlertRepository()
    consent = MockConsentService(default_allowed=True)
    svc = CoachService(
        thread_repo=repo,
        consent_service=consent,
        pro_repo=pro_repo,
        alert_repo=alert_repo,
        safety_classifier=SafetyClassifier(),
    )
    # Mock _get_graph to return safe reply without hitting OpenAI
    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {
        "messages": [AIMessage(content="Scheduled check-in: how are your exercises going?")]
    }
    svc._get_graph = MagicMock(return_value=mock_graph)
    return svc, repo, alert_repo


def _make_active_thread(
    thread_id: str = "t1",
    patient_id: str = "p1",
    goal_confirmed_days_ago: int = 0,
    unanswered_count: int = 0,
    last_coach_days_ago: int = 0,
    checkins_sent: list[int] | None = None,
    phase: CoachPhase = CoachPhase.ACTIVE,
) -> Thread:
    """Create an ACTIVE thread with configurable timing."""
    now = datetime.utcnow()
    return Thread(
        thread_id=thread_id,
        patient_id=patient_id,
        phase=phase,
        goal=Goal(description="Exercise 3x/week", frequency="3x/week"),
        goal_confirmed_at=now - timedelta(days=goal_confirmed_days_ago),
        unanswered_count=unanswered_count,
        last_coach_message_at=now - timedelta(days=last_coach_days_ago),
        last_interaction_at=now - timedelta(days=last_coach_days_ago),
        checkins_sent=checkins_sent or [],
        messages=[
            Message(role=MessageRole.USER, content="I set my goal"),
            Message(role=MessageRole.ASSISTANT, content="Great!"),
        ],
    )


# ═══════════════════════════════════════════════════════════════════════
# Scheduled Check-Ins (Day 2, 5, 7)
# ═══════════════════════════════════════════════════════════════════════

class TestScheduledCheckins:
    def test_day2_checkin_fires_when_due(self):
        svc, repo, *_ = _make_coach()
        thread = _make_active_thread(goal_confirmed_days_ago=3)
        repo.save(thread)

        run_scheduled_checkins(svc, DAY_SECONDS)

        updated = repo.get("t1")
        assert 2 in updated.checkins_sent

    def test_day5_checkin_fires(self):
        svc, repo, *_ = _make_coach()
        thread = _make_active_thread(goal_confirmed_days_ago=6, checkins_sent=[2])
        repo.save(thread)

        run_scheduled_checkins(svc, DAY_SECONDS)

        updated = repo.get("t1")
        assert 5 in updated.checkins_sent

    def test_day7_checkin_fires(self):
        svc, repo, *_ = _make_coach()
        thread = _make_active_thread(goal_confirmed_days_ago=8, checkins_sent=[2, 5])
        repo.save(thread)

        run_scheduled_checkins(svc, DAY_SECONDS)

        updated = repo.get("t1")
        assert 7 in updated.checkins_sent

    def test_checkin_not_sent_before_due(self):
        """Day 2 check-in should NOT fire if only 1 day has passed."""
        svc, repo, *_ = _make_coach()
        thread = _make_active_thread(goal_confirmed_days_ago=1)
        repo.save(thread)

        run_scheduled_checkins(svc, DAY_SECONDS)

        updated = repo.get("t1")
        assert updated.checkins_sent == []

    def test_checkin_not_duplicated(self):
        """Already-sent check-ins should not re-fire."""
        svc, repo, *_ = _make_coach()
        thread = _make_active_thread(goal_confirmed_days_ago=10, checkins_sent=[2, 5, 7])
        repo.save(thread)

        run_scheduled_checkins(svc, DAY_SECONDS)

        updated = repo.get("t1")
        assert updated.checkins_sent == [2, 5, 7]

    def test_skips_thread_without_goal(self):
        svc, repo, *_ = _make_coach()
        thread = Thread(
            thread_id="t-no-goal",
            patient_id="p1",
            phase=CoachPhase.ACTIVE,
            goal=None,
        )
        repo.save(thread)

        run_scheduled_checkins(svc, DAY_SECONDS)
        updated = repo.get("t-no-goal")
        assert updated.checkins_sent == []

    def test_skips_non_active_phase(self):
        svc, repo, *_ = _make_coach()
        thread = _make_active_thread(goal_confirmed_days_ago=3, phase=CoachPhase.ONBOARDING)
        repo.save(thread)

        run_scheduled_checkins(svc, DAY_SECONDS)
        updated = repo.get("t1")
        assert updated.checkins_sent == []

    def test_tone_mapping(self):
        """Verify Day 2 → check-in, Day 5 → nudge, Day 7 → celebration tones."""
        svc, repo, *_ = _make_coach()
        # We test via process_scheduled_checkin directly to inspect the graph call
        thread = _make_active_thread(goal_confirmed_days_ago=3)
        repo.save(thread)
        mock_graph = svc._get_graph()

        svc.process_scheduled_checkin("t1", 2)
        call_state = mock_graph.invoke.call_args[0][0]
        assert call_state["tone"] == "check-in"
        assert call_state["scheduled_checkin_day"] == 2

        mock_graph.reset_mock()
        mock_graph.invoke.return_value = {
            "messages": [AIMessage(content="Keep going!")]
        }
        svc.process_scheduled_checkin("t1", 5)
        call_state = mock_graph.invoke.call_args[0][0]
        assert call_state["tone"] == "nudge"

        mock_graph.reset_mock()
        mock_graph.invoke.return_value = {
            "messages": [AIMessage(content="Amazing week!")]
        }
        svc.process_scheduled_checkin("t1", 7)
        call_state = mock_graph.invoke.call_args[0][0]
        assert call_state["tone"] == "celebration"

    def test_checkin_message_persisted(self):
        svc, repo, *_ = _make_coach()
        thread = _make_active_thread(goal_confirmed_days_ago=3)
        repo.save(thread)

        svc.process_scheduled_checkin("t1", 2)

        updated = repo.get("t1")
        assistant_msgs = [m for m in updated.messages if m.role == MessageRole.ASSISTANT]
        assert len(assistant_msgs) >= 2  # Original + check-in


# ═══════════════════════════════════════════════════════════════════════
# Disengagement Handling
# ═══════════════════════════════════════════════════════════════════════

class TestDisengagement:
    def test_first_nudge_after_1_day(self):
        svc, repo, *_ = _make_coach()
        thread = _make_active_thread(
            unanswered_count=0,
            last_coach_days_ago=2,  # 2 days since last coach msg (> 1 day backoff)
        )
        # Make last message from assistant (user hasn't replied)
        thread.messages.append(Message(role=MessageRole.ASSISTANT, content="How are you?"))
        repo.save(thread)

        run_disengagement_checks(svc, DAY_SECONDS)

        updated = repo.get("t1")
        assert updated.unanswered_count == 1

    def test_second_nudge_after_2_more_days(self):
        svc, repo, *_ = _make_coach()
        thread = _make_active_thread(
            unanswered_count=1,
            last_coach_days_ago=3,  # > 2 day backoff for 2nd nudge
        )
        thread.messages.append(Message(role=MessageRole.ASSISTANT, content="Checking in"))
        repo.save(thread)

        run_disengagement_checks(svc, DAY_SECONDS)

        updated = repo.get("t1")
        assert updated.unanswered_count == 2

    def test_third_unanswered_triggers_dormant(self):
        svc, repo, *_ = _make_coach()
        thread = _make_active_thread(
            unanswered_count=2,
            last_coach_days_ago=4,  # > 3 day backoff for 3rd
        )
        thread.messages.append(Message(role=MessageRole.ASSISTANT, content="Still here"))
        repo.save(thread)

        run_disengagement_checks(svc, DAY_SECONDS)

        updated = repo.get("t1")
        assert updated.phase == CoachPhase.DORMANT
        assert updated.unanswered_count == 3

    def test_dormant_transition_sends_final_message(self):
        svc, repo, *_ = _make_coach()
        thread = _make_active_thread(
            unanswered_count=2,
            last_coach_days_ago=4,
        )
        thread.messages.append(Message(role=MessageRole.ASSISTANT, content="Still here"))
        repo.save(thread)
        msg_count_before = len(thread.messages)

        run_disengagement_checks(svc, DAY_SECONDS)

        updated = repo.get("t1")
        assert len(updated.messages) > msg_count_before
        last_msg = updated.messages[-1]
        assert last_msg.role == MessageRole.ASSISTANT
        assert "ready" in last_msg.content.lower() or "here for you" in last_msg.content.lower()

    def test_no_nudge_if_user_replied(self):
        """If last message is from user, no disengagement needed."""
        svc, repo, *_ = _make_coach()
        thread = _make_active_thread(
            unanswered_count=0,
            last_coach_days_ago=5,
        )
        # Last message is from user — they replied
        thread.messages.append(Message(role=MessageRole.USER, content="I'm doing my exercises"))
        repo.save(thread)

        run_disengagement_checks(svc, DAY_SECONDS)

        updated = repo.get("t1")
        assert updated.unanswered_count == 0  # unchanged

    def test_no_nudge_before_backoff_period(self):
        svc, repo, *_ = _make_coach()
        thread = _make_active_thread(
            unanswered_count=0,
            last_coach_days_ago=0,  # Just messaged — too early for nudge
        )
        thread.messages.append(Message(role=MessageRole.ASSISTANT, content="Hi!"))
        repo.save(thread)

        run_disengagement_checks(svc, DAY_SECONDS)

        updated = repo.get("t1")
        assert updated.unanswered_count == 0

    def test_already_dormant_skipped(self):
        svc, repo, *_ = _make_coach()
        thread = _make_active_thread(
            unanswered_count=3,
            last_coach_days_ago=10,
            phase=CoachPhase.DORMANT,
        )
        thread.messages.append(Message(role=MessageRole.ASSISTANT, content="Final msg"))
        repo.save(thread)

        run_disengagement_checks(svc, DAY_SECONDS)

        # Should not be processed (DORMANT is not in ACTIVE/RE_ENGAGING)
        updated = repo.get("t1")
        assert updated.unanswered_count == 3

    def test_clinician_alert_on_dormant_transition(self):
        """alert_repo.add() should be called when transitioning to DORMANT."""
        svc, repo, alert_repo = _make_coach()
        thread = _make_active_thread(
            unanswered_count=2,
            last_coach_days_ago=4,
        )
        thread.messages.append(Message(role=MessageRole.ASSISTANT, content="Nudge"))
        repo.save(thread)

        svc.process_disengagement_nudge("t1")

        updated = repo.get("t1")
        assert updated.phase == CoachPhase.DORMANT
        # Verify alert was persisted
        alerts = alert_repo.list_by_patient("p1")
        assert len(alerts) == 1
        assert "not responded" in alerts[0].reason


# ═══════════════════════════════════════════════════════════════════════
# Conversation Summarization
# ═══════════════════════════════════════════════════════════════════════

class TestConversationSummaries:
    def test_summary_generated_for_active_thread(self):
        svc, repo, *_ = _make_coach()
        thread = _make_active_thread(goal_confirmed_days_ago=3)
        # Add enough messages
        for i in range(6):
            thread.messages.append(Message(role=MessageRole.USER, content=f"User msg {i}"))
            thread.messages.append(Message(role=MessageRole.ASSISTANT, content=f"Coach msg {i}"))
        thread.last_interaction_at = datetime.utcnow()
        repo.save(thread)

        # Mock the LLM for summarization — patch where it's imported inside the method
        with patch("langchain_openai.ChatOpenAI") as MockLLM:
            mock_llm_instance = MagicMock()
            mock_llm_instance.invoke.return_value = MagicMock(content="Patient is progressing well with their knee exercises.")
            MockLLM.return_value = mock_llm_instance

            svc.summarize_conversation("t1")

        updated = repo.get("t1")
        assert updated.conversation_summary is not None
        assert "progressing" in updated.conversation_summary.lower()
        assert updated.last_summary_at is not None

    def test_summary_skipped_for_short_thread(self):
        svc, repo, *_ = _make_coach()
        thread = Thread(
            thread_id="t-short",
            patient_id="p1",
            phase=CoachPhase.ONBOARDING,
            messages=[Message(role=MessageRole.USER, content="Hi")],
        )
        repo.save(thread)

        svc.summarize_conversation("t-short")

        updated = repo.get("t-short")
        assert updated.conversation_summary is None

    def test_run_conversation_summaries_skips_already_summarized(self):
        svc, repo, *_ = _make_coach()
        now = datetime.utcnow()
        thread = _make_active_thread()
        for i in range(6):
            thread.messages.append(Message(role=MessageRole.USER, content=f"msg {i}"))
            thread.messages.append(Message(role=MessageRole.ASSISTANT, content=f"reply {i}"))
        thread.last_summary_at = now
        thread.last_interaction_at = now - timedelta(minutes=1)  # Interaction BEFORE summary
        repo.save(thread)

        with patch.object(svc, "summarize_conversation") as mock_summarize:
            run_conversation_summaries(svc)
            mock_summarize.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════
# Scheduler Creation
# ═══════════════════════════════════════════════════════════════════════

class TestSchedulerCreation:
    def test_creates_three_jobs(self):
        svc, _, *__ = _make_coach()
        scheduler = create_scheduler(svc, DAY_SECONDS, interval_seconds=60)
        jobs = scheduler.get_jobs()
        job_ids = {j.id for j in jobs}
        assert "scheduled_checkins" in job_ids
        assert "disengagement_checks" in job_ids
        assert "conversation_summaries" in job_ids
        assert len(jobs) == 3
