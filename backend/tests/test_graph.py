"""Tests for LangGraph phase routing, prompt generation, and graph structure."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agent.graph import (
    _system_prompt_for_phase,
    _route_after_agent,
    _extract_goal_from_tool_calls,
    build_graph,
)
from app.agent.state import AgentState
from app.models.domain import CoachPhase


# ═══════════════════════════════════════════════════════════════════════
# Phase-Specific System Prompts
# ═══════════════════════════════════════════════════════════════════════

class TestSystemPromptGeneration:
    def test_onboarding_prompt(self):
        prompt = _system_prompt_for_phase(
            CoachPhase.ONBOARDING.value, None, "t1", "encouraging"
        )
        assert "ONBOARDING" in prompt
        assert "welcome" in prompt.lower()
        assert "goal" in prompt.lower()
        assert "set_goal" in prompt
        assert "never give medical advice" in prompt.lower()

    def test_pending_uses_onboarding_prompt(self):
        prompt = _system_prompt_for_phase(
            CoachPhase.PENDING.value, None, "t1", "encouraging"
        )
        assert "ONBOARDING" in prompt

    def test_active_prompt(self):
        prompt = _system_prompt_for_phase(
            CoachPhase.ACTIVE.value, None, "t1", "encouraging"
        )
        assert "ACTIVE" in prompt
        assert "motivated" in prompt.lower() or "celebrate" in prompt.lower()
        assert "record_pro" in prompt

    def test_re_engaging_prompt(self):
        prompt = _system_prompt_for_phase(
            CoachPhase.RE_ENGAGING.value, None, "t1", "encouraging"
        )
        assert "RE-ENGAGING" in prompt or "RE_ENGAGING" in prompt
        assert "welcome" in prompt.lower() or "returned" in prompt.lower()
        assert "guilt" in prompt.lower() or "gap" in prompt.lower()

    def test_dormant_fallback_prompt(self):
        prompt = _system_prompt_for_phase(
            CoachPhase.DORMANT.value, None, "t1", "encouraging"
        )
        assert "supportive" in prompt.lower()
        assert "never give clinical advice" in prompt.lower()

    def test_program_summary_included(self):
        prompt = _system_prompt_for_phase(
            CoachPhase.ACTIVE.value,
            "Knee stretches 3x10, quad sets 3x10",
            "t1",
        )
        assert "Knee stretches" in prompt

    def test_program_summary_excluded_when_none(self):
        prompt = _system_prompt_for_phase(
            CoachPhase.ACTIVE.value, None, "t1"
        )
        assert "exercise program" not in prompt.lower() or "program:" not in prompt.lower()

    # ─── Personality Tones ────────────────────────────────────────────

    def test_encouraging_tone(self):
        prompt = _system_prompt_for_phase(CoachPhase.ACTIVE.value, None, "t1", "encouraging")
        assert "warm" in prompt.lower() or "upbeat" in prompt.lower()

    def test_direct_tone(self):
        prompt = _system_prompt_for_phase(CoachPhase.ACTIVE.value, None, "t1", "direct")
        assert "concise" in prompt.lower() or "action-oriented" in prompt.lower()

    def test_calm_tone(self):
        prompt = _system_prompt_for_phase(CoachPhase.ACTIVE.value, None, "t1", "calm")
        assert "gentle" in prompt.lower() or "reassuring" in prompt.lower()

    def test_unknown_personality_defaults_to_encouraging(self):
        prompt = _system_prompt_for_phase(CoachPhase.ACTIVE.value, None, "t1", "unknown_tone")
        assert "warm" in prompt.lower() or "upbeat" in prompt.lower()

    # ─── Scheduled Check-In Tone ──────────────────────────────────────

    def test_scheduled_checkin_day_in_prompt(self):
        prompt = _system_prompt_for_phase(
            CoachPhase.ACTIVE.value, None, "t1", "encouraging",
            scheduled_day=5, tone="nudge",
        )
        assert "Day 5" in prompt
        assert "nudge" in prompt

    def test_no_scheduled_context_when_not_checkin(self):
        prompt = _system_prompt_for_phase(
            CoachPhase.ACTIVE.value, None, "t1", "encouraging",
            scheduled_day=None, tone=None,
        )
        assert "scheduled" not in prompt.lower() or "Day " not in prompt

    # ─── Edge Cases in Onboarding Prompt ──────────────────────────────

    def test_onboarding_handles_no_response_edge_case(self):
        prompt = _system_prompt_for_phase(CoachPhase.ONBOARDING.value, None, "t1")
        assert "no worries" in prompt.lower() or "no response" in prompt.lower()

    def test_onboarding_handles_unrealistic_goals(self):
        prompt = _system_prompt_for_phase(CoachPhase.ONBOARDING.value, None, "t1")
        assert "unrealistic" in prompt.lower()

    def test_onboarding_handles_refusal(self):
        prompt = _system_prompt_for_phase(CoachPhase.ONBOARDING.value, None, "t1")
        assert "refuse" in prompt.lower() or "don't want" in prompt.lower()

    def test_onboarding_handles_clinical_mid_flow(self):
        prompt = _system_prompt_for_phase(CoachPhase.ONBOARDING.value, None, "t1")
        assert "clinical" in prompt.lower()
        assert "alert_clinician" in prompt

    # ─── Thread ID in Prompt ──────────────────────────────────────────

    def test_thread_id_embedded_in_prompt(self):
        prompt = _system_prompt_for_phase(CoachPhase.ACTIVE.value, None, "thread-abc-123")
        assert "thread-abc-123" in prompt


# ═══════════════════════════════════════════════════════════════════════
# Routing Logic
# ═══════════════════════════════════════════════════════════════════════

class TestRouteAfterAgent:
    def test_routes_to_tools_when_tool_calls(self):
        ai_msg = AIMessage(content="")
        ai_msg.tool_calls = [{"name": "set_goal", "args": {}, "id": "tc1"}]
        state: AgentState = {"messages": [ai_msg], "phase": "ACTIVE", "thread_id": "t1",
                             "patient_id": "p1", "goal": None, "program_summary": None,
                             "interaction_type": None, "scheduled_checkin_day": None,
                             "tone": None, "personality": None}
        assert _route_after_agent(state) == "tools"

    def test_routes_to_end_when_no_tool_calls(self):
        ai_msg = AIMessage(content="Hello!")
        state: AgentState = {"messages": [ai_msg], "phase": "ACTIVE", "thread_id": "t1",
                             "patient_id": "p1", "goal": None, "program_summary": None,
                             "interaction_type": None, "scheduled_checkin_day": None,
                             "tone": None, "personality": None}
        assert _route_after_agent(state) == "__end__"

    def test_routes_to_end_when_empty_messages(self):
        state: AgentState = {"messages": [], "phase": "ACTIVE", "thread_id": "t1",
                             "patient_id": "p1", "goal": None, "program_summary": None,
                             "interaction_type": None, "scheduled_checkin_day": None,
                             "tone": None, "personality": None}
        assert _route_after_agent(state) == "__end__"

    def test_routes_to_end_for_human_message(self):
        state: AgentState = {"messages": [HumanMessage(content="Hi")], "phase": "ACTIVE",
                             "thread_id": "t1", "patient_id": "p1", "goal": None,
                             "program_summary": None, "interaction_type": None,
                             "scheduled_checkin_day": None, "tone": None, "personality": None}
        assert _route_after_agent(state) == "__end__"


# ═══════════════════════════════════════════════════════════════════════
# Goal Extraction from Tool Calls
# ═══════════════════════════════════════════════════════════════════════

class TestExtractGoalFromToolCalls:
    def test_extracts_goal(self):
        ai_msg = AIMessage(content="Goal set!")
        ai_msg.tool_calls = [{"name": "set_goal", "args": {"description": "Walk daily", "frequency": "daily"}, "id": "tc1"}]
        state: AgentState = {"messages": [HumanMessage(content="Hi"), ai_msg],
                             "phase": "ONBOARDING", "thread_id": "t1",
                             "patient_id": "p1", "goal": None, "program_summary": None,
                             "interaction_type": None, "scheduled_checkin_day": None,
                             "tone": None, "personality": None}
        result = _extract_goal_from_tool_calls(state)
        assert result is not None
        assert result["description"] == "Walk daily"
        assert result["frequency"] == "daily"

    def test_no_goal_without_set_goal_call(self):
        ai_msg = AIMessage(content="Here's your program")
        ai_msg.tool_calls = [{"name": "get_program_summary", "args": {}, "id": "tc1"}]
        state: AgentState = {"messages": [ai_msg], "phase": "ONBOARDING",
                             "thread_id": "t1", "patient_id": "p1", "goal": None,
                             "program_summary": None, "interaction_type": None,
                             "scheduled_checkin_day": None, "tone": None, "personality": None}
        result = _extract_goal_from_tool_calls(state)
        assert result is None

    def test_no_goal_without_tool_calls(self):
        ai_msg = AIMessage(content="Tell me your goal")
        state: AgentState = {"messages": [ai_msg], "phase": "ONBOARDING",
                             "thread_id": "t1", "patient_id": "p1", "goal": None,
                             "program_summary": None, "interaction_type": None,
                             "scheduled_checkin_day": None, "tone": None, "personality": None}
        result = _extract_goal_from_tool_calls(state)
        assert result is None

    def test_extracts_from_last_ai_message(self):
        """If multiple AI messages, should extract from the latest set_goal call."""
        ai_msg1 = AIMessage(content="First try")
        ai_msg1.tool_calls = [{"name": "set_goal", "args": {"description": "Old goal"}, "id": "tc1"}]
        ai_msg2 = AIMessage(content="Updated")
        ai_msg2.tool_calls = [{"name": "set_goal", "args": {"description": "New goal"}, "id": "tc2"}]
        state: AgentState = {"messages": [ai_msg1, ai_msg2], "phase": "ONBOARDING",
                             "thread_id": "t1", "patient_id": "p1", "goal": None,
                             "program_summary": None, "interaction_type": None,
                             "scheduled_checkin_day": None, "tone": None, "personality": None}
        result = _extract_goal_from_tool_calls(state)
        assert result["description"] == "New goal"
