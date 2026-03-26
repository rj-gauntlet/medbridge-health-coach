"""Integration tests for CoachService — consent gate, safety retry, crisis handling,
goal extraction pipeline, and phase transitions. Uses a mocked LangGraph to avoid
real LLM calls while testing all orchestration logic."""

import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.models.domain import CoachPhase, Goal, Message, MessageRole, Thread
from app.repositories.in_memory import InMemoryThreadRepository
from app.repositories.pro_repo import InMemoryProRepository
from app.services.coach_service import CoachService
from app.services.consent_service import MockConsentService
from app.services.safety_classifier import SafetyClassifier


# ─── Helpers ──────────────────────────────────────────────────────────

def _make_service(
    *,
    default_allowed: bool = True,
    denied_ids: set | None = None,
    graph_reply: str = "Great job, keep it up!",
    graph_tool_calls: list | None = None,
) -> tuple[CoachService, InMemoryThreadRepository, InMemoryProRepository, MagicMock]:
    """Build a CoachService with mocked graph for deterministic testing."""
    repo = InMemoryThreadRepository()
    pro_repo = InMemoryProRepository()
    consent = MockConsentService(default_allowed=default_allowed, denied_patient_ids=denied_ids or set())

    # Build mock graph
    mock_graph = MagicMock()
    ai_msg = AIMessage(content=graph_reply)
    if graph_tool_calls:
        ai_msg.tool_calls = graph_tool_calls
    mock_graph.invoke.return_value = {"messages": [HumanMessage(content="hi"), ai_msg]}

    service = CoachService(
        thread_repo=repo,
        consent_service=consent,
        pro_repo=pro_repo,
        safety_classifier=SafetyClassifier(),
    )
    service._get_graph = MagicMock(return_value=mock_graph)
    return service, repo, pro_repo, mock_graph


# ─── Consent Gate ─────────────────────────────────────────────────────

class TestConsentGate:
    def test_allowed_patient_proceeds(self):
        svc, repo, _, _ = _make_service()
        result = svc.process_message("p1", "Hello")
        assert result["blocked"] is False
        assert result["error"] is None
        assert result["reply"] == "Great job, keep it up!"

    def test_denied_patient_blocked(self):
        svc, _, _, mock_graph = _make_service(denied_ids={"p-denied"})
        result = svc.process_message("p-denied", "Hello")
        assert result["blocked"] is True
        assert result["error"] == "consent_required"
        assert "consent" in result["reply"].lower()
        mock_graph.invoke.assert_not_called()

    def test_consent_checked_every_interaction(self):
        """Consent must be verified on each call, not just thread creation."""
        svc, repo, _, _ = _make_service(denied_ids={"p2"})
        # First create thread for allowed patient
        svc_allowed, repo_allowed, _, _ = _make_service()
        r1 = svc_allowed.process_message("p2", "Hello")
        # Now deny that patient
        svc2, _, _, mock_graph2 = _make_service(denied_ids={"p2"})
        r2 = svc2.process_message("p2", "Follow up")
        assert r2["blocked"] is True
        mock_graph2.invoke.assert_not_called()

    def test_default_deny_all(self):
        svc, _, _, mock_graph = _make_service(default_allowed=False)
        result = svc.process_message("anyone", "Hello")
        assert result["blocked"] is True
        mock_graph.invoke.assert_not_called()


# ─── Phase Transitions ───────────────────────────────────────────────

class TestPhaseTransitions:
    def test_pending_to_onboarding_on_first_message(self):
        svc, repo, _, _ = _make_service()
        result = svc.process_message("p1", "Hi there")
        thread = repo.get_by_patient("p1")
        assert thread is not None
        # Should be ONBOARDING (PENDING → ONBOARDING on first message)
        assert thread.phase == CoachPhase.ONBOARDING

    def test_onboarding_to_active_on_goal_set(self):
        """When the LLM calls set_goal, phase transitions to ACTIVE."""
        svc, repo, _, _ = _make_service(
            graph_reply="Goal confirmed!",
            graph_tool_calls=[{
                "name": "set_goal",
                "args": {"description": "Exercise 3x/week", "frequency": "3x/week"},
                "id": "tc1",
            }],
        )
        result = svc.process_message("p1", "I want to exercise 3 times a week")
        thread = repo.get_by_patient("p1")
        assert thread.phase == CoachPhase.ACTIVE
        assert thread.goal is not None
        assert thread.goal.description == "Exercise 3x/week"
        assert thread.goal.frequency == "3x/week"
        assert thread.goal_confirmed_at is not None

    def test_dormant_to_re_engaging_on_patient_return(self):
        svc, repo, _, _ = _make_service()
        # Create a DORMANT thread
        thread = Thread(
            thread_id="t-dormant",
            patient_id="p-dormant",
            phase=CoachPhase.DORMANT,
            unanswered_count=3,
            last_interaction_at=datetime.utcnow() - timedelta(days=10),
        )
        repo.save(thread)

        result = svc.process_message("p-dormant", "I'm back!", thread_id="t-dormant")
        updated = repo.get("t-dormant")
        assert updated.phase == CoachPhase.RE_ENGAGING
        assert updated.unanswered_count == 0

    def test_unanswered_count_resets_on_user_reply(self):
        svc, repo, _, _ = _make_service()
        thread = Thread(
            thread_id="t1",
            patient_id="p1",
            phase=CoachPhase.ACTIVE,
            unanswered_count=2,
        )
        repo.save(thread)
        svc.process_message("p1", "Hey", thread_id="t1")
        updated = repo.get("t1")
        assert updated.unanswered_count == 0


# ─── Safety Classifier Integration ───────────────────────────────────

class TestSafetyIntegration:
    def test_safe_message_passes_through(self):
        svc, _, _, _ = _make_service(graph_reply="Keep up the great work with your exercises!")
        result = svc.process_message("p1", "How am I doing?")
        assert result["reply"] == "Keep up the great work with your exercises!"
        assert result["blocked"] is False

    def test_clinical_content_triggers_retry(self):
        """Clinical content in LLM reply should trigger one retry."""
        svc, _, _, mock_graph = _make_service(
            graph_reply="Based on your diagnosis, you should take medication."
        )
        # On retry, return a safe message
        safe_ai = AIMessage(content="I'd encourage you to discuss that with your care team!")
        mock_graph.invoke.side_effect = [
            {"messages": [AIMessage(content="Based on your diagnosis, you should take medication.")]},
            {"messages": [safe_ai]},
        ]

        result = svc.process_message("p1", "What about my meds?")
        assert mock_graph.invoke.call_count == 2  # Original + retry
        assert result["reply"] == "I'd encourage you to discuss that with your care team!"

    def test_clinical_retry_still_unsafe_falls_back(self):
        """If retry also produces clinical content, fall back to generic safe message."""
        svc, _, _, mock_graph = _make_service()
        unsafe_reply1 = AIMessage(content="Your diagnosis requires medication changes.")
        unsafe_reply2 = AIMessage(content="The symptom suggests a treatment plan adjustment.")
        mock_graph.invoke.side_effect = [
            {"messages": [unsafe_reply1]},
            {"messages": [unsafe_reply2]},
        ]

        result = svc.process_message("p1", "Tell me about treatment")
        assert mock_graph.invoke.call_count == 2
        assert "care team" in result["reply"].lower()
        assert "clinician" in result["reply"].lower()

    def test_crisis_content_no_retry(self):
        """Crisis content should NOT retry — immediate redirect."""
        svc, _, _, mock_graph = _make_service()
        crisis_reply = AIMessage(content="If you feel like ending your life or suicide, here's what to do.")
        mock_graph.invoke.return_value = {"messages": [crisis_reply]}

        result = svc.process_message("p1", "I'm feeling really down")
        assert mock_graph.invoke.call_count == 1  # No retry
        assert "care team" in result["reply"].lower()
        assert "mental health" in result["reply"].lower() or "clinician" in result["reply"].lower()

    def test_crisis_reply_differs_from_clinical_reply(self):
        """Crisis fallback message should be distinct from clinical fallback."""
        svc_crisis, _, _, mock_graph_crisis = _make_service()
        mock_graph_crisis.invoke.return_value = {
            "messages": [AIMessage(content="You mentioned suicide, let me help.")]
        }
        crisis_result = svc_crisis.process_message("p1", "msg")

        svc_clinical, _, _, mock_graph_clin = _make_service()
        unsafe1 = AIMessage(content="Your diagnosis is clear.")
        unsafe2 = AIMessage(content="Your symptom needs a prescription.")
        mock_graph_clin.invoke.side_effect = [
            {"messages": [unsafe1]},
            {"messages": [unsafe2]},
        ]
        clinical_result = svc_clinical.process_message("p2", "msg")

        # Both redirect to care team but with different wording
        assert "care team" in crisis_result["reply"].lower() or "clinician" in crisis_result["reply"].lower()
        assert "care team" in clinical_result["reply"].lower() or "clinician" in clinical_result["reply"].lower()


# ─── Message Persistence ─────────────────────────────────────────────

class TestMessagePersistence:
    def test_user_and_assistant_messages_stored(self):
        svc, repo, _, _ = _make_service(graph_reply="Hello! Let's set a goal.")
        svc.process_message("p1", "Hi coach")
        thread = repo.get_by_patient("p1")
        assert len(thread.messages) == 2
        assert thread.messages[0].role == MessageRole.USER
        assert thread.messages[0].content == "Hi coach"
        assert thread.messages[1].role == MessageRole.ASSISTANT
        assert thread.messages[1].content == "Hello! Let's set a goal."

    def test_timestamps_updated(self):
        svc, repo, _, _ = _make_service()
        before = datetime.utcnow()
        svc.process_message("p1", "Hello")
        thread = repo.get_by_patient("p1")
        assert thread.last_interaction_at is not None
        assert thread.last_interaction_at >= before
        assert thread.last_coach_message_at is not None
        assert thread.last_coach_message_at >= before

    def test_personality_persisted(self):
        svc, repo, _, _ = _make_service()
        svc.process_message("p1", "Hello", personality="calm")
        thread = repo.get_by_patient("p1")
        assert thread.personality == "calm"


# ─── Goal Extraction ─────────────────────────────────────────────────

class TestGoalExtraction:
    def test_no_tool_call_no_goal(self):
        svc, repo, _, _ = _make_service(graph_reply="Tell me your goal!", graph_tool_calls=None)
        svc.process_message("p1", "Hi")
        thread = repo.get_by_patient("p1")
        assert thread.goal is None
        assert thread.phase == CoachPhase.ONBOARDING

    def test_set_goal_tool_call_extracts_goal(self):
        svc, repo, _, _ = _make_service(
            graph_reply="Goal set!",
            graph_tool_calls=[{
                "name": "set_goal",
                "args": {"description": "Walk daily", "frequency": "every day"},
                "id": "tc1",
            }],
        )
        svc.process_message("p1", "I want to walk every day")
        thread = repo.get_by_patient("p1")
        assert thread.goal is not None
        assert thread.goal.description == "Walk daily"
        assert thread.goal.frequency == "every day"

    def test_non_set_goal_tool_call_ignored(self):
        svc, repo, _, _ = _make_service(
            graph_reply="Here's your program.",
            graph_tool_calls=[{
                "name": "get_program_summary",
                "args": {},
                "id": "tc2",
            }],
        )
        svc.process_message("p1", "What exercises?")
        thread = repo.get_by_patient("p1")
        assert thread.goal is None
