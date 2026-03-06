"""APScheduler jobs: scheduled check-ins and disengagement handling."""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.models.domain import CoachPhase

if TYPE_CHECKING:
    from app.services.coach_service import CoachService

# Backoff days for disengagement: 1st nudge after 1 day, 2nd after 2 more, 3rd after 3 more
DISENGAGEMENT_BACKOFF_DAYS = [1, 2, 3]
SCHEDULED_CHECKIN_DAYS = [2, 5, 7]


def run_scheduled_checkins(coach: "CoachService", day_seconds: int) -> None:
    """Run Day 2, 5, 7 check-ins for ACTIVE threads that are due."""
    now = datetime.utcnow()
    threads = coach.thread_repo.list_threads_by_phases([CoachPhase.ACTIVE])

    for thread in threads:
        if not thread.goal or not thread.goal_confirmed_at:
            continue
        goal_at = thread.goal_confirmed_at

        for day in SCHEDULED_CHECKIN_DAYS:
            if day in (thread.checkins_sent or []):
                continue
            # Is it time? goal_confirmed_at + day days
            due_at = goal_at + timedelta(seconds=day * day_seconds)
            if now >= due_at:
                coach.process_scheduled_checkin(thread.thread_id, day)


def run_disengagement_checks(coach: "CoachService", day_seconds: int) -> None:
    """Check for unanswered messages and send nudges or transition to DORMANT."""
    now = datetime.utcnow()
    threads = coach.thread_repo.list_threads_by_phases([CoachPhase.ACTIVE, CoachPhase.RE_ENGAGING])

    for thread in threads:
        if not thread.last_coach_message_at:
            continue
        # Last message must be from coach (user hasn't replied)
        if thread.messages and thread.messages[-1].role.value == "user":
            continue  # User replied, no disengagement
        if thread.unanswered_count >= 3:
            continue  # Already dormant
        if thread.phase == CoachPhase.DORMANT:
            continue

        backoff_idx = min(thread.unanswered_count, 2)
        backoff_seconds = DISENGAGEMENT_BACKOFF_DAYS[backoff_idx] * day_seconds
        due_at = thread.last_coach_message_at + timedelta(seconds=backoff_seconds)
        if now >= due_at:
            coach.process_disengagement_nudge(thread.thread_id)


def create_scheduler(coach: "CoachService", day_seconds: int, interval_seconds: int = 60) -> BackgroundScheduler:
    """Create and configure the scheduler. Runs every interval_seconds (default 60s)."""
    scheduler = BackgroundScheduler()

    def checkins():
        run_scheduled_checkins(coach, day_seconds)

    def disengagement():
        run_disengagement_checks(coach, day_seconds)

    scheduler.add_job(checkins, IntervalTrigger(seconds=interval_seconds), id="scheduled_checkins")
    scheduler.add_job(disengagement, IntervalTrigger(seconds=interval_seconds), id="disengagement_checks")
    return scheduler
