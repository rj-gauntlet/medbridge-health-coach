"""PRO (Patient-Reported Outcome) repository."""

import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

from app.models.domain import PatientReportedOutcome


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
