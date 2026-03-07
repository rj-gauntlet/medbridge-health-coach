"""State schema for the LangGraph agent. Must be compatible with LangGraph StateGraph."""

from typing import Annotated, Literal, Optional, TypedDict

from langgraph.graph import add_messages


# LangGraph expects a TypedDict or similar for state
class AgentState(TypedDict):
    """State passed through the LangGraph. Mirrors Thread domain model for graph execution."""

    messages: Annotated[list, add_messages]
    phase: str  # PENDING | ONBOARDING | ACTIVE | RE_ENGAGING | DORMANT
    goal: Optional[dict]  # {"description": str, "frequency": Optional[str]}
    thread_id: str
    patient_id: str
    # For tool execution context
    program_summary: Optional[str]
    interaction_type: Optional[str]  # "user_message" | "scheduled_checkin" | "re_engagement"
    scheduled_checkin_day: Optional[int]  # 2, 5, or 7
    tone: Optional[str]  # "check-in" | "nudge" | "celebration"
    personality: Optional[str]  # "encouraging" | "direct" | "calm"
