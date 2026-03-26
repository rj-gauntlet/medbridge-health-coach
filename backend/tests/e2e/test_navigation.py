"""E2E tests for cross-page navigation and theme persistence."""

from datetime import datetime

from app.models.domain import CoachPhase, Message, MessageRole, Thread


def test_chat_to_exercises(page, base_url):
    """Clicking 'View exercises' navigates to /exercises."""
    page.goto(base_url)
    page.click("a[href='/exercises']")
    page.wait_for_url("**/exercises")
    assert "/exercises" in page.url


def test_exercises_to_chat(page, base_url):
    """Clicking 'Back to Chat' navigates to /."""
    page.goto(f"{base_url}/exercises")
    page.click("a[href='/']")
    page.wait_for_url(f"{base_url}/")
    assert page.url.rstrip("/").endswith(base_url.rstrip("/").split(":")[-1])


def test_chat_to_dashboard(page, base_url, thread_repo):
    """Clicking 'Clinician Dashboard' link navigates to /dashboard."""
    # Seed data so status bar with dashboard link is visible
    thread_repo.save(Thread(
        thread_id="t-nav",
        patient_id="patient-001",
        phase=CoachPhase.ACTIVE,
        messages=[Message(role=MessageRole.USER, content="Hi")],
        last_interaction_at=datetime.utcnow(),
    ))
    page.goto(base_url)
    page.click("#loadBtn")
    page.wait_for_selector(".dashboard-link")
    page.click(".dashboard-link")
    page.wait_for_url("**/dashboard")
    assert "/dashboard" in page.url


def test_theme_persists_across_pages(page, base_url):
    """Toggling theme on chat page persists to dashboard via localStorage."""
    page.goto(base_url)
    # Should start light
    initial_theme = page.locator("html").get_attribute("data-theme")
    assert initial_theme == "light"

    # Toggle to dark
    page.click(".theme-toggle")
    assert page.locator("html").get_attribute("data-theme") == "dark"

    # Navigate to dashboard — theme should persist
    page.goto(f"{base_url}/dashboard")
    assert page.locator("html").get_attribute("data-theme") == "dark"
