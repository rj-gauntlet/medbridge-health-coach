"""Tool definitions for the AI Health Coach. LLM can call these autonomously."""

from typing import Optional

from langchain_core.tools import tool


@tool
def set_goal(description: str, frequency: Optional[str] = None) -> str:
    """Store the patient's exercise goal. Call this when the patient has stated and confirmed their goal.
    description: The goal in the patient's words (e.g., 'Do my knee exercises 3 times a week').
    frequency: How often they plan to exercise (e.g., '3 times per week', 'daily')."""
    # Stub: actual persistence happens via state update in the graph
    return f"Goal stored: {description}" + (f" (frequency: {frequency})" if frequency else "")


@tool
def set_reminder(days: int, message: str) -> str:
    """Schedule a reminder for the patient.
    days: Number of days from now for the reminder.
    message: The reminder message to send."""
    return f"Reminder scheduled for {days} days from now."


@tool
def get_program_summary() -> str:
    """Get a summary of the patient's assigned exercise program. Call this when you need to reference their exercises."""
    # Stub: returns mock data; in production would fetch from MedBridge
    return "Your program includes: knee extension stretches (3x10), quad sets (3x10), and heel slides (3x10). Perform as prescribed by your clinician."


@tool
def get_adherence_summary() -> str:
    """Get a summary of the patient's adherence to their exercise program so far."""
    # Stub: returns mock data
    return "Adherence data not yet available. Keep going!"


@tool
def alert_clinician(reason: str, urgency: str = "normal") -> str:
    """Alert the patient's care team. Use for: clinical questions, mental health crisis, or after 3 unanswered messages.
    reason: Why the clinician is being alerted.
    urgency: 'normal', 'high', or 'crisis'."""
    return f"Clinician alerted: {reason} (urgency: {urgency})"


def get_coach_tools():
    """Return the list of tools for the coach LLM."""
    return [set_goal, set_reminder, get_program_summary, get_adherence_summary, alert_clinician]
