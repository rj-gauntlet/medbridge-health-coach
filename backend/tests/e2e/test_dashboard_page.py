"""E2E tests for the Clinician Dashboard page (/dashboard)."""

from datetime import datetime

from app.models.domain import CoachPhase, Message, MessageRole, Thread


def test_dashboard_loads_empty(page, base_url):
    """Dashboard with no patients shows empty message."""
    page.goto(f"{base_url}/dashboard")
    page.wait_for_selector("#empty:not([style*='display: none']), .patient-row", timeout=5000)
    empty = page.locator("#empty")
    if empty.is_visible():
        assert "No patients" in empty.inner_text()


def test_dashboard_shows_patients(page, base_url, thread_repo):
    """Dashboard renders a row for each patient thread."""
    thread_repo.save(Thread(
        thread_id="t-d1",
        patient_id="patient-001",
        phase=CoachPhase.ACTIVE,
        messages=[Message(role=MessageRole.USER, content="Hi")],
        last_interaction_at=datetime.utcnow(),
    ))
    thread_repo.save(Thread(
        thread_id="t-d2",
        patient_id="patient-002",
        phase=CoachPhase.ONBOARDING,
        last_interaction_at=datetime.utcnow(),
    ))
    page.goto(f"{base_url}/dashboard")
    page.wait_for_selector(".patient-row")
    rows = page.locator(".patient-row")
    assert rows.count() == 2


def test_expand_drawer(page, base_url, thread_repo):
    """Clicking Details expands the drawer with conversation info."""
    thread_repo.save(Thread(
        thread_id="t-drawer",
        patient_id="patient-drawer",
        phase=CoachPhase.ACTIVE,
        conversation_summary="Patient is making good progress.",
        messages=[Message(role=MessageRole.USER, content="Hello")],
        last_interaction_at=datetime.utcnow(),
    ))
    page.goto(f"{base_url}/dashboard")
    page.wait_for_selector(".patient-row")
    page.locator(".expand-btn").first.click()
    page.wait_for_selector(".drawer-row")
    assert page.locator(".drawer-row").count() == 1


def test_collapse_drawer(page, base_url, thread_repo):
    """Clicking Details again collapses the drawer."""
    thread_repo.save(Thread(
        thread_id="t-collapse",
        patient_id="patient-collapse",
        phase=CoachPhase.ACTIVE,
        messages=[Message(role=MessageRole.USER, content="Hi")],
        last_interaction_at=datetime.utcnow(),
    ))
    page.goto(f"{base_url}/dashboard")
    page.wait_for_selector(".patient-row")
    page.locator(".expand-btn").first.click()
    page.wait_for_selector(".drawer-row")
    # Click again to collapse
    page.locator(".expand-btn").first.click()
    page.wait_for_timeout(500)
    assert page.locator(".drawer-row").count() == 0
