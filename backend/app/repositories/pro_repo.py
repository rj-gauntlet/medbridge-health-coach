"""PRO (Patient-Reported Outcome) and Clinician Alert repositories."""

import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

from app.models.domain import ClinicianAlert, PatientReportedOutcome


class IProRepository(ABC):
    """Abstract interface for PRO persistence."""

    @abstractmethod
    def add(self, pro: PatientReportedOutcome) -> PatientReportedOutcome:
        pass

    @abstractmethod
    def list_by_thread(self, thread_id: str, limit: int = 30) -> list[PatientReportedOutcome]:
        pass


class InMemoryProRepository(IProRepository):
    """In-memory PRO repository for testing."""

    def __init__(self) -> None:
        self._pros: list[PatientReportedOutcome] = []

    def add(self, pro: PatientReportedOutcome) -> PatientReportedOutcome:
        self._pros.append(pro)
        return pro

    def list_by_thread(self, thread_id: str, limit: int = 30) -> list[PatientReportedOutcome]:
        return [p for p in self._pros if p.thread_id == thread_id][-limit:]


def _extract_db_path(database_url: str) -> str:
    if database_url.startswith("sqlite:///"):
        return database_url.replace("sqlite:///", "")
    return database_url


class SQLiteProRepository(IProRepository):
    """SQLite-backed PRO repository."""

    def __init__(self, database_url: str) -> None:
        self._path = _extract_db_path(database_url)
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path)

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pros (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id TEXT NOT NULL,
                    pain INTEGER,
                    difficulty INTEGER,
                    adherence_rating INTEGER,
                    note TEXT,
                    recorded_at TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pros_thread ON pros(thread_id)")

    def add(self, pro: PatientReportedOutcome) -> PatientReportedOutcome:
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO pros (thread_id, pain, difficulty, adherence_rating, note, recorded_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    pro.thread_id,
                    pro.pain,
                    pro.difficulty,
                    pro.adherence_rating,
                    pro.note,
                    pro.recorded_at.isoformat(),
                ),
            )
        return pro

    def list_by_thread(self, thread_id: str, limit: int = 30) -> list[PatientReportedOutcome]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT thread_id, pain, difficulty, adherence_rating, note, recorded_at
                   FROM pros WHERE thread_id = ? ORDER BY recorded_at DESC LIMIT ?""",
                (thread_id, limit),
            ).fetchall()
        result = []
        for r in rows:
            recorded_at = datetime.fromisoformat(r[5].replace("Z", "+00:00")) if r[5] else datetime.utcnow()
            result.append(
                PatientReportedOutcome(
                    thread_id=r[0],
                    pain=r[1],
                    difficulty=r[2],
                    adherence_rating=r[3],
                    note=r[4],
                    recorded_at=recorded_at,
                )
            )
        return result


# ── Clinician Alert Repository ──


class IAlertRepository(ABC):
    """Abstract interface for clinician alert persistence."""

    @abstractmethod
    def add(self, alert: ClinicianAlert) -> ClinicianAlert:
        pass

    @abstractmethod
    def list_by_patient(self, patient_id: str, limit: int = 20) -> list[ClinicianAlert]:
        pass

    @abstractmethod
    def list_all(self, limit: int = 100) -> list[ClinicianAlert]:
        pass


class InMemoryAlertRepository(IAlertRepository):
    """In-memory alert repository for testing."""

    def __init__(self) -> None:
        self._alerts: list[ClinicianAlert] = []
        self._next_id = 1

    def add(self, alert: ClinicianAlert) -> ClinicianAlert:
        alert.id = self._next_id
        self._next_id += 1
        self._alerts.append(alert)
        return alert

    def list_by_patient(self, patient_id: str, limit: int = 20) -> list[ClinicianAlert]:
        matches = [a for a in self._alerts if a.patient_id == patient_id]
        return sorted(matches, key=lambda a: a.created_at, reverse=True)[:limit]

    def list_all(self, limit: int = 100) -> list[ClinicianAlert]:
        return sorted(self._alerts, key=lambda a: a.created_at, reverse=True)[:limit]


class SQLiteAlertRepository(IAlertRepository):
    """SQLite-backed clinician alert repository."""

    def __init__(self, database_url: str) -> None:
        self._path = _extract_db_path(database_url)
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path)

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id TEXT NOT NULL,
                    patient_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    urgency TEXT NOT NULL DEFAULT 'normal',
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_patient ON alerts(patient_id)")

    def add(self, alert: ClinicianAlert) -> ClinicianAlert:
        with self._conn() as conn:
            cursor = conn.execute(
                """INSERT INTO alerts (thread_id, patient_id, reason, urgency, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (alert.thread_id, alert.patient_id, alert.reason, alert.urgency, alert.created_at.isoformat()),
            )
            alert.id = cursor.lastrowid
        return alert

    def list_by_patient(self, patient_id: str, limit: int = 20) -> list[ClinicianAlert]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT id, thread_id, patient_id, reason, urgency, created_at
                   FROM alerts WHERE patient_id = ? ORDER BY created_at DESC LIMIT ?""",
                (patient_id, limit),
            ).fetchall()
        return [self._row_to_alert(r) for r in rows]

    def list_all(self, limit: int = 100) -> list[ClinicianAlert]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT id, thread_id, patient_id, reason, urgency, created_at
                   FROM alerts ORDER BY created_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [self._row_to_alert(r) for r in rows]

    @staticmethod
    def _row_to_alert(r: tuple) -> ClinicianAlert:
        created_at = datetime.fromisoformat(r[5].replace("Z", "+00:00")) if r[5] else datetime.utcnow()
        return ClinicianAlert(id=r[0], thread_id=r[1], patient_id=r[2], reason=r[3], urgency=r[4], created_at=created_at)
