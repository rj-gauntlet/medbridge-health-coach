"""SQLite implementation of thread repository."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.models.domain import CoachPhase, Goal, Message, MessageRole, Thread
from app.repositories.interfaces import IThreadRepository


def _extract_db_path(database_url: str) -> str:
    """Extract file path from sqlite:///... URL."""
    if database_url.startswith("sqlite:///"):
        return database_url.replace("sqlite:///", "")
    return database_url


class SQLiteThreadRepository(IThreadRepository):
    """SQLite-backed thread repository."""

    def __init__(self, database_url: str) -> None:
        self._path = _extract_db_path(database_url)
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path)

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS threads (
                    thread_id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    messages_json TEXT NOT NULL DEFAULT '[]',
                    goal_json TEXT,
                    unanswered_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    last_interaction_at TEXT,
                    goal_confirmed_at TEXT,
                    last_coach_message_at TEXT,
                    checkins_sent_json TEXT NOT NULL DEFAULT '[]'
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_threads_patient ON threads(patient_id)"
            )
            # Migrate: add new columns if missing
            try:
                conn.execute("ALTER TABLE threads ADD COLUMN goal_confirmed_at TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE threads ADD COLUMN last_coach_message_at TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE threads ADD COLUMN checkins_sent_json TEXT DEFAULT '[]'")
            except sqlite3.OperationalError:
                pass

    def _row_to_thread(self, row: dict) -> Thread:
        r = row if isinstance(row, dict) else {}
        thread_id = r.get("thread_id")
        patient_id = r.get("patient_id")
        phase = r.get("phase")
        messages_json = r.get("messages_json")
        goal_json = r.get("goal_json")
        unanswered_count = r.get("unanswered_count", 0)
        created_at = r.get("created_at")
        last_interaction_at = r.get("last_interaction_at")
        goal_confirmed_at = r.get("goal_confirmed_at")
        last_coach_message_at = r.get("last_coach_message_at")
        checkins_sent_json = r.get("checkins_sent_json", "[]")

        messages = []
        for m in json.loads(messages_json or "[]"):
            messages.append(
                Message(role=MessageRole(m["role"]), content=m["content"])
            )
        goal = None
        if goal_json:
            g = json.loads(goal_json)
            goal = Goal(description=g["description"], frequency=g.get("frequency"))
        def _parse_dt(s: Optional[str]) -> Optional[datetime]:
            if not s:
                return None
            try:
                return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
            except (ValueError, TypeError):
                return None

        checkins_sent = json.loads(checkins_sent_json or "[]")

        return Thread(
            thread_id=thread_id,
            patient_id=patient_id,
            phase=CoachPhase(phase),
            messages=messages,
            goal=goal,
            unanswered_count=unanswered_count or 0,
            created_at=_parse_dt(created_at) or datetime.utcnow(),
            last_interaction_at=_parse_dt(last_interaction_at),
            goal_confirmed_at=_parse_dt(goal_confirmed_at),
            last_coach_message_at=_parse_dt(last_coach_message_at),
            checkins_sent=checkins_sent,
        )

    def get(self, thread_id: str) -> Optional[Thread]:
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM threads WHERE thread_id = ?", (thread_id,)
            ).fetchone()
            if not row:
                return None
            return self._row_to_thread(dict(row) if row else {})

    def get_by_patient(self, patient_id: str) -> Optional[Thread]:
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM threads WHERE patient_id = ? ORDER BY created_at DESC LIMIT 1",
                (patient_id,),
            ).fetchone()
            if not row:
                return None
            return self._row_to_thread(dict(row) if row else {})

    def save(self, thread: Thread) -> Thread:
        messages_json = json.dumps(
            [{"role": m.role.value, "content": m.content} for m in thread.messages]
        )
        goal_json = None
        if thread.goal:
            goal_json = json.dumps(
                {"description": thread.goal.description, "frequency": thread.goal.frequency}
            )
        checkins_sent_json = json.dumps(getattr(thread, "checkins_sent", []) or [])
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO threads (thread_id, patient_id, phase, messages_json, goal_json, unanswered_count, created_at, last_interaction_at, goal_confirmed_at, last_coach_message_at, checkins_sent_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(thread_id) DO UPDATE SET
                    phase = excluded.phase,
                    messages_json = excluded.messages_json,
                    goal_json = excluded.goal_json,
                    unanswered_count = excluded.unanswered_count,
                    last_interaction_at = excluded.last_interaction_at,
                    goal_confirmed_at = excluded.goal_confirmed_at,
                    last_coach_message_at = excluded.last_coach_message_at,
                    checkins_sent_json = excluded.checkins_sent_json
                """,
                (
                    thread.thread_id,
                    thread.patient_id,
                    thread.phase.value,
                    messages_json,
                    goal_json,
                    thread.unanswered_count,
                    thread.created_at.isoformat(),
                    thread.last_interaction_at.isoformat() if thread.last_interaction_at else None,
                    thread.goal_confirmed_at.isoformat() if getattr(thread, "goal_confirmed_at", None) else None,
                    thread.last_coach_message_at.isoformat() if getattr(thread, "last_coach_message_at", None) else None,
                    checkins_sent_json,
                ),
            )
        return thread

    def add_message(self, thread_id: str, message: Message) -> None:
        t = self.get(thread_id)
        if not t:
            return
        t.messages.append(message)
        self.save(t)

    def update_phase(self, thread_id: str, phase: CoachPhase) -> None:
        t = self.get(thread_id)
        if not t:
            return
        t.phase = phase
        self.save(t)

    def update_goal(self, thread_id: str, goal: Goal) -> None:
        t = self.get(thread_id)
        if not t:
            return
        t.goal = goal
        self.save(t)

    def update_unanswered_count(self, thread_id: str, count: int) -> None:
        t = self.get(thread_id)
        if not t:
            return
        t.unanswered_count = count
        self.save(t)

    def update_goal_confirmed_at(self, thread_id: str, dt: datetime) -> None:
        t = self.get(thread_id)
        if not t:
            return
        t.goal_confirmed_at = dt
        self.save(t)

    def update_last_coach_message_at(self, thread_id: str, dt: datetime) -> None:
        t = self.get(thread_id)
        if not t:
            return
        t.last_coach_message_at = dt
        self.save(t)

    def update_checkins_sent(self, thread_id: str, sent: list[int]) -> None:
        t = self.get(thread_id)
        if not t:
            return
        t.checkins_sent = sent
        self.save(t)

    def list_threads_by_phases(self, phases: list[CoachPhase]) -> list[Thread]:
        phase_vals = [p.value for p in phases]
        placeholders = ",".join("?" * len(phase_vals))
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"SELECT * FROM threads WHERE phase IN ({placeholders})",
                phase_vals,
            ).fetchall()
            return [self._row_to_thread(dict(r)) for r in rows] if rows else []
