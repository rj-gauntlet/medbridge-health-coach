"""API route tests."""

import os
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

# Ensure minimal config for app load (scheduler won't call LLM during quick tests)
os.environ.setdefault("OPENAI_API_KEY", "sk-test-placeholder")

from app.main import app
from app.models.domain import CoachPhase, Message, MessageRole, Thread


@pytest.fixture
def mock_coach_service():
    """Mock coach service that returns canned responses."""
    mock = MagicMock()
    mock.process_message.return_value = {
        "reply": "Mock reply from coach",
        "thread_id": "thread-123",
        "phase": CoachPhase.ACTIVE.value,
        "blocked": False,
        "error": None,
    }
    return mock


@pytest.fixture
def mock_thread_repo():
    """In-memory repo for API tests."""
    from app.repositories.in_memory import InMemoryThreadRepository
    return InMemoryThreadRepository()


@pytest.fixture
def client(mock_coach_service, mock_thread_repo):
    """Test client with overridden dependencies."""
    from app.api.deps import get_coach_service, get_thread_repository

    def override_coach():
        return mock_coach_service

    def override_repo():
        return mock_thread_repo

    app.dependency_overrides[get_coach_service] = override_coach
    app.dependency_overrides[get_thread_repository] = override_repo
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_get_thread_empty(client):
    resp = client.get("/api/thread?patient_id=unknown")
    assert resp.status_code == 200
    data = resp.json()
    assert data["thread_id"] is None
    assert data["phase"] == "PENDING"
    assert data["messages"] == []


def test_get_thread_with_data(client, mock_thread_repo):
    thread = Thread(
        thread_id="t1",
        patient_id="p1",
        phase=CoachPhase.ACTIVE,
        messages=[
            Message(role=MessageRole.USER, content="Hi"),
            Message(role=MessageRole.ASSISTANT, content="Hello!"),
        ],
    )
    mock_thread_repo.save(thread)

    resp = client.get("/api/thread?patient_id=p1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["thread_id"] == "t1"
    assert data["phase"] == "ACTIVE"
    assert len(data["messages"]) == 2
    assert data["messages"][0]["role"] == "user"
    assert data["messages"][0]["content"] == "Hi"
    assert data["messages"][1]["role"] == "assistant"
    assert data["messages"][1]["content"] == "Hello!"


def test_chat_success(client, mock_coach_service):
    resp = client.post(
        "/api/chat",
        json={"patient_id": "p1", "message": "Hi"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["reply"] == "Mock reply from coach"
    assert data["thread_id"] == "thread-123"
    assert data["phase"] == "ACTIVE"
    assert data["blocked"] is False
    mock_coach_service.process_message.assert_called_once_with(
        patient_id="p1",
        user_message="Hi",
        thread_id=None,
    )


def test_chat_with_thread_id(client, mock_coach_service):
    resp = client.post(
        "/api/chat",
        json={"patient_id": "p1", "message": "Hi", "thread_id": "existing-thread"},
    )
    assert resp.status_code == 200
    mock_coach_service.process_message.assert_called_once_with(
        patient_id="p1",
        user_message="Hi",
        thread_id="existing-thread",
    )
