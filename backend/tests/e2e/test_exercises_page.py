"""E2E tests for the Exercise Library page (/exercises)."""


def test_exercises_page_loads(page, base_url):
    """Page renders with 3 exercise cards."""
    page.goto(f"{base_url}/exercises")
    cards = page.locator(".exercise-card")
    assert cards.count() == 3


def test_exercise_card_content(page, base_url):
    """Cards show correct exercise titles."""
    page.goto(f"{base_url}/exercises")
    titles = page.locator(".exercise-card h2")
    assert titles.nth(0).inner_text() == "Knee Extension Stretch"
    assert titles.nth(1).inner_text() == "Quad Sets"
    assert titles.nth(2).inner_text() == "Heel Slides"
