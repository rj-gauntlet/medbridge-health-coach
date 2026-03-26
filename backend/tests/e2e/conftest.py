"""E2E test fixtures: live FastAPI server with mocked dependencies."""

import os
import socket
import threading
import time
from unittest.mock import MagicMock

import pytest
import uvicorn

# Set placeholder key before any app imports
os.environ.setdefault("OPENAI_API_KEY", "sk-test-placeholder")

from app.main import app
from app.api.deps import get_coach_service, get_thread_repository, get_pro_repository
from app.repositories.in_memory import InMemoryThreadRepository
from app.repositories.pro_repo import InMemoryProRepository


# ── Mutable module-level state shared with the running server ──

_thread_repo = InMemoryThreadRepository()
_pro_repo = InMemoryProRepository()
_mock_coach = MagicMock()

_DEFAULT_CHAT_RESPONSE = {
    "reply": "Mock coach reply — great job!",
    "thread_id": "thread-e2e-001",
    "phase": "ONBOARDING",
    "blocked": False,
    "error": None,
}

_mock_coach.process_message.return_value = _DEFAULT_CHAT_RESPONSE

# Wire overrides into the FastAPI app
app.dependency_overrides[get_thread_repository] = lambda: _thread_repo
app.dependency_overrides[get_pro_repository] = lambda: _pro_repo
app.dependency_overrides[get_coach_service] = lambda: _mock_coach


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def live_server():
    """Start a real uvicorn server in a daemon thread for E2E tests."""
    port = _find_free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for server to accept connections
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            sock = socket.create_connection(("127.0.0.1", port), timeout=0.5)
            sock.close()
            break
        except OSError:
            time.sleep(0.1)
    else:
        raise RuntimeError("E2E server did not start within 15 seconds")

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(autouse=True)
def reset_state():
    """Reset in-memory repos and mock between tests."""
    _thread_repo._threads.clear()
    _pro_repo._pros.clear()
    _mock_coach.reset_mock()
    _mock_coach.process_message.return_value = dict(_DEFAULT_CHAT_RESPONSE)


@pytest.fixture(scope="session")
def base_url(live_server):
    return live_server


@pytest.fixture
def thread_repo():
    return _thread_repo


@pytest.fixture
def pro_repo():
    return _pro_repo


@pytest.fixture
def mock_coach():
    return _mock_coach
