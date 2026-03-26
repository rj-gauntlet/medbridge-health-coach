"""Clinician dashboard and PRO API routes."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_alert_repository, get_pro_repository, get_thread_repository
from app.models.domain import CoachPhase
from app.repositories.pro_repo import IAlertRepository, IProRepository
from app.repositories.interfaces import IThreadRepository

router = APIRouter(prefix="/api", tags=["dashboard"])


class AlertItem(BaseModel):
    reason: str
    urgency: str
    created_at: str


class PatientSummary(BaseModel):
    thread_id: str
    patient_id: str
    phase: str
    goal: str | None
    last_interaction_at: str | None
    unanswered_count: int
    at_risk: bool
    conversation_summary: str | None
    alerts: list[AlertItem] = []


class DashboardResponse(BaseModel):
    patients: list[PatientSummary]
    total: int


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(
    repo: IThreadRepository = Depends(get_thread_repository),
    alert_repo: IAlertRepository = Depends(get_alert_repository),
) -> DashboardResponse:
    """Clinician dashboard: all patients with phase, adherence, alerts."""
    threads = repo.list_all()
    now = __import__("datetime").datetime.utcnow()
    patients = []
    for t in threads:
        at_risk = (
            t.phase in (CoachPhase.ACTIVE, CoachPhase.RE_ENGAGING)
            and t.unanswered_count >= 1
            and t.last_coach_message_at
            and (now - t.last_coach_message_at).days >= 2
        )
        patient_alerts = alert_repo.list_by_patient(t.patient_id, limit=5)
        patients.append(
            PatientSummary(
                thread_id=t.thread_id,
                patient_id=t.patient_id,
                phase=t.phase.value,
                goal=t.goal.description if t.goal else None,
                last_interaction_at=t.last_interaction_at.isoformat() if t.last_interaction_at else None,
                unanswered_count=t.unanswered_count,
                at_risk=at_risk,
                conversation_summary=getattr(t, "conversation_summary", None),
                alerts=[
                    AlertItem(reason=a.reason, urgency=a.urgency, created_at=a.created_at.isoformat())
                    for a in patient_alerts
                ],
            )
        )
    return DashboardResponse(patients=patients, total=len(patients))


@router.get("/alerts")
def get_alerts(
    patient_id: str | None = None,
    alert_repo: IAlertRepository = Depends(get_alert_repository),
) -> list[AlertItem]:
    """Get alert history, optionally filtered by patient."""
    if patient_id:
        alerts = alert_repo.list_by_patient(patient_id, limit=50)
    else:
        alerts = alert_repo.list_all(limit=100)
    return [
        AlertItem(reason=a.reason, urgency=a.urgency, created_at=a.created_at.isoformat())
        for a in alerts
    ]


class ProItem(BaseModel):
    pain: int | None
    difficulty: int | None
    adherence_rating: int | None
    recorded_at: str


@router.get("/pros")
def get_pros(
    thread_id: str,
    pro_repo: IProRepository = Depends(get_pro_repository),
) -> list[ProItem]:
    """Get PRO history for a thread."""
    pros = pro_repo.list_by_thread(thread_id, limit=30)
    return [
        ProItem(
            pain=p.pain,
            difficulty=p.difficulty,
            adherence_rating=p.adherence_rating,
            recorded_at=p.recorded_at.isoformat(),
        )
        for p in pros
    ]
