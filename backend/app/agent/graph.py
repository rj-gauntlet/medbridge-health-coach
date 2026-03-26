"""LangGraph main router and agent. Phase-based routing to subgraphs."""

from typing import Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

from app.agent.state import AgentState
from app.agent.tools import get_coach_tools
from app.config import get_settings
from app.models.domain import CoachPhase


def _system_prompt_for_phase(phase: str, program_summary: str | None, thread_id: str, personality: str = "encouraging", scheduled_day: int | None = None, tone: str | None = None) -> str:
    """Build system prompt based on phase and context."""
    tone_map = {
        "encouraging": "Warm, upbeat, and celebratory. Use lots of positive reinforcement.",
        "direct": "Clear, concise, and action-oriented. Get to the point.",
        "calm": "Gentle, measured, and reassuring. Avoid hype.",
    }
    personality_tone = tone_map.get(personality, tone_map["encouraging"])
    base = f"""You are a friendly, supportive AI health coach for MedBridge. You help patients stick to their home exercise program. Tone: {personality_tone}
You are NOT a clinician—never give medical advice, diagnose, or prescribe. Redirect medical questions to their care team.

Current thread_id: {thread_id}. When calling get_adherence_summary, record_pro, or get_streak, always pass thread_id="{thread_id}".

"""
    if program_summary:
        base += f"The patient's exercise program: {program_summary}\n\n"

    if phase == CoachPhase.PENDING.value or phase == CoachPhase.ONBOARDING.value:
        base += """You are in ONBOARDING. Your goals:
1. Welcome the patient warmly
2. Reference their assigned exercises (use get_program_summary if needed)
3. Ask them to set an exercise goal in their own words (e.g., "I want to do my exercises 3 times a week")
4. Extract a structured goal from their response
5. Confirm the goal with them
6. When confirmed, call set_goal with their goal description and frequency

Edge cases—handle gracefully:
- No response or empty message: Briefly acknowledge ("No worries—when you're ready, just share your goal.") and re-invite. Don't repeat long prompts.
- Very short or vague answers (e.g., "ok", "idk"): Gently ask for specifics: "What would a realistic exercise schedule look like for you—e.g., 3 times a week?"
- Unrealistic goals (e.g., "10 hours a day", "every hour"): Gently suggest something more achievable. E.g., "That might be tough to sustain—how about starting with 3 times a week?"
- Patient refuses to set a goal ("I don't want to", "maybe later"): Respect their choice. Say you're here when they're ready. Do not pressure or guilt.
- Clinical questions mid-flow (symptoms, meds, diagnosis, treatment): Do NOT answer. Use alert_clinician and redirect: "I'm here for motivation and accountability, not medical advice. Your care team can help with that."
"""
    elif phase == CoachPhase.ACTIVE.value:
        base += """You are in ACTIVE mode. The patient has set a goal. Keep them motivated, celebrate progress, and gently nudge if needed.
Periodically ask: "On a scale of 1-10, how was your pain today?" or "How difficult were the exercises (1-10)?" When they answer, call record_pro to store it.
Use get_adherence_summary and get_streak to reference progress. Celebrate streaks.
"""
        if scheduled_day and tone:
            base += f"\nThis is a scheduled Day {scheduled_day} check-in. Use a {tone} tone. Reference their goal and encourage them.\n"
    elif phase == CoachPhase.RE_ENGAGING.value:
        base += """You are in RE-ENGAGING mode. The patient was dormant and has returned. Warmly welcome them back, acknowledge the gap without guilt, and encourage them to pick up where they left off. Re-reference their goal if helpful.
"""
    else:
        base += """Be supportive and encouraging. Reference their goal when relevant. Never give clinical advice.
"""
    return base


def _convert_to_langchain_messages(thread_messages: list) -> list[BaseMessage]:
    """Convert our Message model to LangChain format."""
    result = []
    for m in thread_messages:
        if m.role.value == "user":
            result.append(HumanMessage(content=m.content))
        elif m.role.value == "assistant":
            result.append(AIMessage(content=m.content))
        elif m.role.value == "system":
            result.append(SystemMessage(content=m.content))
    return result


def _create_agent_node(llm, tools):
    """Create the agent node that calls LLM with tools."""
    llm_with_tools = llm.bind_tools(tools)
    tool_node = ToolNode(tools)

    def agent_node(state: AgentState) -> dict:
        messages = state["messages"]
        phase = state.get("phase", CoachPhase.ONBOARDING.value)
        program_summary = state.get("program_summary")
        thread_id = state.get("thread_id", "")
        personality = state.get("personality") or "encouraging"
        scheduled_day = state.get("scheduled_checkin_day")
        tone = state.get("tone")
        sys_prompt = _system_prompt_for_phase(phase, program_summary, thread_id, personality, scheduled_day, tone)
        full_messages = [SystemMessage(content=sys_prompt)] + list(messages)
        response = llm_with_tools.invoke(full_messages)
        return {"messages": [response]}

    return agent_node, tool_node


def _route_after_agent(state: AgentState) -> Literal["tools", "__end__"]:
    """Route to tools if the last message has tool_calls, else END."""
    messages = state.get("messages", [])
    if not messages:
        return "__end__"
    last = messages[-1]
    if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
        return "tools"
    return "__end__"


def _extract_goal_from_tool_calls(state: AgentState) -> dict | None:
    """Extract goal from set_goal tool call for state update."""
    messages = state.get("messages", [])
    for m in reversed(messages):
        if isinstance(m, AIMessage) and getattr(m, "tool_calls", None):
            for tc in m.tool_calls:
                if tc.get("name") == "set_goal":
                    args = tc.get("args", {})
                    return {
                        "description": args.get("description", ""),
                        "frequency": args.get("frequency"),
                    }
    return None


def build_graph(thread_repo=None, pro_repo=None, alert_repo=None, thread_id: str = "", patient_id: str = ""):
    """Build and compile the LangGraph. Returns compiled graph."""
    settings = get_settings()
    tools = get_coach_tools(thread_repo=thread_repo, pro_repo=pro_repo, alert_repo=alert_repo, thread_id=thread_id, patient_id=patient_id)
    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0.7,
    )
    agent_node, tool_node = _create_agent_node(llm, tools)

    graph_builder = StateGraph(AgentState)

    graph_builder.add_node("agent", agent_node)
    graph_builder.add_node("tools", tool_node)

    graph_builder.add_edge(START, "agent")
    graph_builder.add_conditional_edges("agent", _route_after_agent)
    graph_builder.add_edge("tools", "agent")

    return graph_builder.compile()


def create_agent_graph():
    """Factory for the compiled graph. Use this for dependency injection."""
    return build_graph()
