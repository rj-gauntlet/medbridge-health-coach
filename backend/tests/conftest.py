"""Pytest fixtures."""

import pytest

from app.repositories.in_memory import InMemoryThreadRepository
from app.repositories.sqlite_repo import SQLiteThreadRepository
from app.services.consent_service import MockConsentService
from app.services.coach_service import CoachService
from app.services.safety_classifier import SafetyClassifier


@pytest.fixture
def in_memory_repo():
    """In-memory thread repository for fast unit tests."""
    return InMemoryThreadRepository()


@pytest.fixture
def sqlite_repo(request):
    """SQLite repository using a unique DB file per test (in workspace)."""
    from pathlib import Path
    tests_dir = Path(__file__).parent
    name = request.node.name.replace("[", "_").replace("]", "_").replace("::", "_")
    db_path = tests_dir / f".test_{name}.db"
    repo = SQLiteThreadRepository(f"sqlite:///{db_path}")
    yield repo
    try:
        db_path.unlink(missing_ok=True)
    except PermissionError:
        pass


@pytest.fixture
def consent_service():
    """Default consent service (all allowed)."""
    return MockConsentService(default_allowed=True)


@pytest.fixture
def consent_service_denied():
    """Consent service with patient-999 denied."""
    return MockConsentService(default_allowed=True, denied_patient_ids={"patient-999"})


@pytest.fixture
def safety_classifier():
    return SafetyClassifier()


@pytest.fixture
def coach_service(in_memory_repo, consent_service):
    """Coach service with in-memory repo (no LLM calls in tests)."""
    return CoachService(
        thread_repo=in_memory_repo,
        consent_service=consent_service,
        safety_classifier=SafetyClassifier(),
    )
