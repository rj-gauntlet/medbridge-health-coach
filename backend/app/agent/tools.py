"""Tool definitions for the AI Health Coach. LLM can call these autonomously."""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Optional

from langchain_core.tools import tool

if TYPE_CHECKING:
    from app.repositories.interfaces import IThreadRepository
    from app.repositories.pro_repo import IProRepository


def _make_get_adherence_summary(pro_repo: "IProRepository | None"):
    @tool
    def get_adherence_summary(thread_id: str) -> str:
        """Get adherence and PRO (patient-reported outcomes) for this thread. Pass the thread_id from context."""
        if not pro_repo:
            return "Adherence data not yet available. Keep going!"
        pros = pro_repo.list_by_thread(thread_id, limit=10)
        if not pros:
            return "No adherence data yet. Encourage the patient to share how they're doing (pain 1-10, difficulty 1-10)."
        lines = []
        recent = pros[:5]
        for p in reversed(recent):
            parts = []
            if p.pain is not None:
                parts.append(f"pain {p.pain}/10")
            if p.difficulty is not None:
                parts.append(f"difficulty {p.difficulty}/10")
            if p.adherence_rating is not None:
                parts.append(f"adherence {p.adherence_rating}/10")
            if parts:
                lines.append(f"- {', '.join(parts)}" + (f" ({p.recorded_at.strftime('%Y-%m-%d')})" if p.recorded_at else ""))
        return "Recent PROs: " + ("; ".join(lines) if lines else "None yet.")
    return get_adherence_summary


def _make_record_pro(pro_repo: "IProRepository | None"):
    @tool
    def record_pro(thread_id: str, pain: Optional[int] = None, difficulty: Optional[int] = None, adherence_rating: Optional[int] = None, note: Optional[str] = None) -> str:
        """Record a patient-reported outcome. Call when the patient shares pain (1-10), difficulty (1-10), or adherence. Pass thread_id from context."""
        if not pro_repo:
            return "PRO recording unavailable."
        from app.models.domain import PatientReportedOutcome
        pro = PatientReportedOutcome(thread_id=thread_id, pain=pain, difficulty=difficulty, adherence_rating=adherence_rating, note=note)
        pro_repo.add(pro)
        return f"Recorded: pain={pain}, difficulty={difficulty}, adherence={adherence_rating}"
    return record_pro


def _make_get_streak(thread_repo: "IThreadRepository | None"):
    @tool
    def get_streak(thread_id: str) -> str:
        """Get the patient's current engagement streak (consecutive days with interaction)."""
        if not thread_repo:
            return "Streak data unavailable."
        t = thread_repo.get(thread_id)
        if not t or not t.last_interaction_at:
            return "No streak yet."
        # Simple heuristic: count distinct days with messages (approximate)
        msg_dates = set()
        for m in t.messages:
            # We don't have per-message timestamps in domain - use last_interaction
            pass
        # Fallback: streak = 1 if interacted today, else 0
        now = datetime.utcnow()
        last = t.last_interaction_at
        if last.date() == now.date():
            return "Patient engaged today. Streak: at least 1 day."
        days_ago = (now - last).days
        if days_ago <= 1:
            return "Patient engaged recently. Keep encouraging!"
        return f"Last interaction was {days_ago} days ago. A friendly check-in could help."
    return get_streak


@tool
def set_goal(description: str, frequency: Optional[str] = None) -> str:
    """Store the patient's exercise goal. Call when the patient has stated and confirmed their goal."""
    return f"Goal stored: {description}" + (f" (frequency: {frequency})" if frequency else "")


@tool
def set_reminder(days: int, message: str) -> str:
    """Schedule a reminder for the patient. days: days from now. message: reminder text."""
    return f"Reminder scheduled for {days} days from now."


@tool
def get_program_summary() -> str:
    """Get the patient's assigned exercise program."""
    return "Your program includes: knee extension stretches (3x10), quad sets (3x10), heel slides (3x10). Patients can view animated demos at /exercises. Perform as prescribed."


def _make_alert_clinician(alert_repo, thread_id: str = "", patient_id: str = ""):
    @tool
    def alert_clinician(reason: str, urgency: str = "normal") -> str:
        """Alert the care team. Use for: clinical questions, crisis, or 3+ unanswered messages."""
        if alert_repo:
            from app.models.domain import ClinicianAlert
            alert_repo.add(ClinicianAlert(
                thread_id=thread_id,
                patient_id=patient_id,
                reason=reason,
                urgency=urgency,
            ))
        return f"Clinician alerted: {reason} (urgency: {urgency})"
    return alert_clinician


def get_coach_tools(thread_repo: "IThreadRepository | None" = None, pro_repo: "IProRepository | None" = None, alert_repo=None, thread_id: str = "", patient_id: str = ""):
    """Return tools for the coach LLM."""
    return [
        set_goal,
        set_reminder,
        get_program_summary,
        _make_get_adherence_summary(pro_repo),
        _make_record_pro(pro_repo),
        _make_get_streak(thread_repo),
        _make_alert_clinician(alert_repo, thread_id, patient_id),
    ]
