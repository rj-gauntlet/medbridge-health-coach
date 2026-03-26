"""Tests for clinician alert persistence — repo, tool, service, and dashboard."""

import sqlite3
import tempfile
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.models.domain import (
    ClinicianAlert,
    CoachPhase,
    Goal,
    Message,
    MessageRole,
    Thread,
)
from app.repositories.pro_repo import (
    IAlertRepository,
    InMemoryAlertRepository,
    SQLiteAlertRepository,
)


# ── InMemoryAlertRepository ──


class TestInMemoryAlertRepo:
    def test_add_and_list_by_patient(self):
        repo = InMemoryAlertRepository()
        a = ClinicianAlert(thread_id="t1", patient_id="p1", reason="test reason", urgency="normal")
        result = repo.add(a)
        assert result.id == 1
        alerts = repo.list_by_patient("p1")
        assert len(alerts) == 1
        assert alerts[0].reason == "test reason"

    def test_list_by_patient_filters(self):
        repo = InMemoryAlertRepository()
        repo.add(ClinicianAlert(thread_id="t1", patient_id="p1", reason="r1"))
        repo.add(ClinicianAlert(thread_id="t2", patient_id="p2", reason="r2"))
        assert len(repo.list_by_patient("p1")) == 1
        assert len(repo.list_by_patient("p2")) == 1
        assert len(repo.list_by_patient("p3")) == 0

    def test_list_all_ordered_by_created_at(self):
        repo = InMemoryAlertRepository()
        repo.add(ClinicianAlert(thread_id="t1", patient_id="p1", reason="old", created_at=datetime(2026, 1, 1)))
        repo.add(ClinicianAlert(thread_id="t2", patient_id="p2", reason="new", created_at=datetime(2026, 3, 1)))
        all_alerts = repo.list_all()
        assert len(all_alerts) == 2
        assert all_alerts[0].reason == "new"  # Most recent first

    def test_list_all_respects_limit(self):
        repo = InMemoryAlertRepository()
        for i in range(10):
            repo.add(ClinicianAlert(thread_id="t1", patient_id="p1", reason=f"r{i}"))
        assert len(repo.list_all(limit=3)) == 3

    def test_high_urgency(self):
        repo = InMemoryAlertRepository()
        repo.add(ClinicianAlert(thread_id="t1", patient_id="p1", reason="crisis", urgency="high"))
        alert = repo.list_by_patient("p1")[0]
        assert alert.urgency == "high"


# ── SQLiteAlertRepository ──


class TestSQLiteAlertRepo:
    def _make_repo(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        return SQLiteAlertRepository(f"sqlite:///{db_path}")

    def test_add_and_list(self, tmp_path):
        repo = self._make_repo(tmp_path)
        a = ClinicianAlert(thread_id="t1", patient_id="p1", reason="test", urgency="normal")
        result = repo.add(a)
        assert result.id is not None
        alerts = repo.list_by_patient("p1")
        assert len(alerts) == 1
        assert alerts[0].reason == "test"
        assert alerts[0].thread_id == "t1"

    def test_list_all(self, tmp_path):
        repo = self._make_repo(tmp_path)
        repo.add(ClinicianAlert(thread_id="t1", patient_id="p1", reason="r1"))
        repo.add(ClinicianAlert(thread_id="t2", patient_id="p2", reason="r2"))
        assert len(repo.list_all()) == 2

    def test_schema_created(self, tmp_path):
        repo = self._make_repo(tmp_path)
        db_path = str(tmp_path / "test.db")
        conn = sqlite3.connect(db_path)
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = [t[0] for t in tables]
        assert "alerts" in table_names
        conn.close()


# ── alert_clinician tool with repo ──


class TestAlertClinicianTool:
    def test_persists_to_repo(self):
        repo = InMemoryAlertRepository()
        from app.agent.tools import _make_alert_clinician
        alert_tool = _make_alert_clinician(repo, thread_id="t1", patient_id="p1")
        result = alert_tool.invoke({"reason": "crisis detected", "urgency": "high"})
        assert "Clinician alerted" in result
        alerts = repo.list_by_patient("p1")
        assert len(alerts) == 1
        assert alerts[0].reason == "crisis detected"
        assert alerts[0].urgency == "high"

    def test_no_repo_still_works(self):
        from app.agent.tools import _make_alert_clinician
        alert_tool = _make_alert_clinician(None, thread_id="t1", patient_id="p1")
        result = alert_tool.invoke({"reason": "test", "urgency": "normal"})
        assert "Clinician alerted" in result


# ── CoachService disengagement creates alert ──


class TestDisengagementAlert:
    def _make_service(self):
        from app.services.coach_service import CoachService
        from app.services.consent_service import MockConsentService

        thread_repo = MagicMock()
        consent = MockConsentService(default_allowed=True)
        alert_repo = InMemoryAlertRepository()

        service = CoachService(
            thread_repo=thread_repo,
            consent_service=consent,
            alert_repo=alert_repo,
        )
        return service, thread_repo, alert_repo

    def test_dormant_transition_creates_alert(self):
        service, thread_repo, alert_repo = self._make_service()

        thread = Thread(
            thread_id="t1",
            patient_id="p1",
            phase=CoachPhase.ACTIVE,
            unanswered_count=2,
            goal=Goal(description="Exercise 3x/week"),
        )
        thread_repo.get.return_value = thread

        service.process_disengagement_nudge("t1")

        # Alert should have been persisted
        alerts = alert_repo.list_by_patient("p1")
        assert len(alerts) == 1
        assert "not responded" in alerts[0].reason
        assert alerts[0].urgency == "normal"

    def test_nudge_before_dormant_no_alert(self):
        service, thread_repo, alert_repo = self._make_service()

        thread = Thread(
            thread_id="t1",
            patient_id="p1",
            phase=CoachPhase.ACTIVE,
            unanswered_count=0,
            goal=Goal(description="Exercise 3x/week"),
        )
        thread_repo.get.return_value = thread

        # Mock the graph to avoid LLM call
        with patch.object(service, '_get_graph') as mock_graph:
            mock_result = {"messages": [MagicMock(content="Hey, checking in!", tool_calls=None)]}
            mock_graph.return_value.invoke.return_value = mock_result
            with patch.object(service, '_extract_reply', return_value="Hey, checking in!"):
                service.process_disengagement_nudge("t1")

        # No alert for first nudge
        alerts = alert_repo.list_by_patient("p1")
        assert len(alerts) == 0
