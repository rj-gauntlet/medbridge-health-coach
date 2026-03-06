"""FastAPI dependencies: service wiring."""

from functools import lru_cache

from fastapi import Depends

from app.config import get_settings
from app.repositories.interfaces import IThreadRepository
from app.repositories.sqlite_repo import SQLiteThreadRepository
from app.services.coach_service import CoachService
from app.services.consent_service import IConsentService, MockConsentService
from app.services.safety_classifier import SafetyClassifier


def get_thread_repository() -> IThreadRepository:
    settings = get_settings()
    return SQLiteThreadRepository(settings.database_url)


def get_consent_service() -> IConsentService:
    return MockConsentService(default_allowed=True)


def get_coach_service(
    thread_repo: IThreadRepository = Depends(get_thread_repository),
    consent_service: IConsentService = Depends(get_consent_service),
) -> CoachService:
    return CoachService(
        thread_repo=thread_repo,
        consent_service=consent_service,
        safety_classifier=SafetyClassifier(),
    )
