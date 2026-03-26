"""E2E tests for the Chat page (/)."""

import json
from datetime import datetime

from app.models.domain import CoachPhase, Goal, Message, MessageRole, Thread


def test_chat_page_loads(page, base_url):
    """Chat page renders all key interactive elements."""
    page.goto(base_url)
    assert page.locator("#patientId").is_visible()
    assert page.locator("#personalitySelect").is_visible()
    assert page.locator("#loadBtn").is_visible()
    assert page.locator("#messageInput").is_visible()
    assert page.locator("#sendBtn").is_visible()
    assert page.locator(".theme-toggle").is_visible()


def test_load_patient_empty(page, base_url):
    """Loading a patient with no thread shows empty state."""
    page.goto(base_url)
    page.fill("#patientId", "patient-new")
    page.click("#loadBtn")
    page.wait_for_selector(".empty-state")
    assert "No messages yet" in page.locator(".empty-state").inner_text()


def test_load_patient_with_history(page, base_url, thread_repo):
    """Loading a patient with existing messages renders them."""
    thread_repo.save(Thread(
        thread_id="t-hist",
        patient_id="patient-hist",
        phase=CoachPhase.ACTIVE,
        messages=[
            Message(role=MessageRole.USER, content="Hello coach"),
            Message(role=MessageRole.ASSISTANT, content="Welcome! How are you?"),
        ],
        last_interaction_at=datetime.utcnow(),
    ))
    page.goto(base_url)
    page.fill("#patientId", "patient-hist")
    page.click("#loadBtn")
    page.wait_for_selector(".message.user")
    assert page.locator(".message.user").count() >= 1
    assert page.locator(".message.coach").count() >= 1
    assert "Hello coach" in page.locator(".message.user").first.inner_text()
    assert "Welcome! How are you?" in page.locator(".message.coach").first.inner_text()


def _intercept_chat_and_thread(page, base_url, coach_reply, thread_id="thread-e2e"):
    """Set up route interception for /api/chat and subsequent /api/thread reload."""
    chat_response = json.dumps({
        "reply": coach_reply,
        "thread_id": thread_id,
        "phase": "ONBOARDING",
        "blocked": False,
        "error": None,
    })
    thread_response = json.dumps({
        "thread_id": thread_id,
        "phase": "ONBOARDING",
        "messages": [
            {"role": "user", "content": "placeholder", "created_at": datetime.utcnow().isoformat() + "Z"},
            {"role": "assistant", "content": coach_reply, "created_at": datetime.utcnow().isoformat() + "Z"},
        ],
        "goal": None,
        "personality": "encouraging",
        "streak_days": None,
    })

    def handle_chat(route):
        route.fulfill(
            status=200,
            content_type="application/json",
            body=chat_response,
        )

    def handle_thread(route):
        route.fulfill(
            status=200,
            content_type="application/json",
            body=thread_response,
        )

    page.route("**/api/chat", handle_chat)
    page.route("**/api/thread*", handle_thread)


def test_send_message_and_receive_reply(page, base_url):
    """Sending a message shows user bubble then coach reply."""
    user_msg = "Hi there"
    coach_reply = "Great to hear from you!"

    page.goto(base_url)

    # Intercept chat POST and thread GET with the real message content
    chat_response = json.dumps({
        "reply": coach_reply,
        "thread_id": "thread-send",
        "phase": "ONBOARDING",
        "blocked": False,
        "error": None,
    })
    thread_response = json.dumps({
        "thread_id": "thread-send",
        "phase": "ONBOARDING",
        "messages": [
            {"role": "user", "content": user_msg, "created_at": datetime.utcnow().isoformat() + "Z"},
            {"role": "assistant", "content": coach_reply, "created_at": datetime.utcnow().isoformat() + "Z"},
        ],
        "goal": None,
        "personality": "encouraging",
        "streak_days": None,
    })
    page.route("**/api/chat", lambda route: route.fulfill(
        status=200, content_type="application/json", body=chat_response,
    ))
    page.route("**/api/thread*", lambda route: route.fulfill(
        status=200, content_type="application/json", body=thread_response,
    ))

    page.fill("#messageInput", user_msg)
    page.click("#sendBtn")

    # Wait for messages to render (either from client-side add or thread reload)
    page.wait_for_selector(".message.coach:not(.typing)", timeout=10000)

    # Verify both user and coach messages are present
    all_text = page.locator("#chat").inner_text()
    assert user_msg in all_text, f"User message not found in chat: {all_text}"
    assert coach_reply in all_text, f"Coach reply not found in chat: {all_text}"


def test_status_bar_updates(page, base_url, thread_repo):
    """Status bar shows phase badge and goal when thread is loaded."""
    thread_repo.save(Thread(
        thread_id="t-status",
        patient_id="patient-status",
        phase=CoachPhase.ACTIVE,
        goal=Goal(description="Knee exercises", frequency="3 times a week"),
        messages=[Message(role=MessageRole.ASSISTANT, content="Keep it up!")],
        last_interaction_at=datetime.utcnow(),
    ))
    page.goto(base_url)
    page.fill("#patientId", "patient-status")
    page.click("#loadBtn")
    page.wait_for_selector("#statusBar:not([style*='display: none'])")
    badge_text = page.locator("#phaseBadge").inner_text()
    assert "ACTIVE" in badge_text.upper()
    goal_text = page.locator("#goalDisplay").inner_text()
    assert "Knee exercises" in goal_text


def test_personality_select(page, base_url):
    """Changing personality dropdown and sending passes it to the API."""
    page.goto(base_url)

    # Capture the request body to verify personality is sent
    captured_body = {}

    def capture_chat(route):
        request = route.request
        body = json.loads(request.post_data)
        captured_body.update(body)
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({
                "reply": "Direct response.",
                "thread_id": "thread-pers",
                "phase": "ONBOARDING",
                "blocked": False,
                "error": None,
            }),
        )

    # Also intercept thread reload so it doesn't wipe messages
    page.route("**/api/chat", capture_chat)
    page.route("**/api/thread*", lambda route: route.fulfill(
        status=200,
        content_type="application/json",
        body=json.dumps({
            "thread_id": "thread-pers",
            "phase": "ONBOARDING",
            "messages": [],
            "goal": None,
            "personality": "direct",
            "streak_days": None,
        }),
    ))

    page.select_option("#personalitySelect", "direct")
    page.fill("#messageInput", "test personality")
    page.click("#sendBtn")
    page.wait_for_selector(".message.user", timeout=5000)

    # Verify the request included personality=direct
    assert captured_body.get("personality") == "direct"
