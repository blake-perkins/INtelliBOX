"""E2E tests for global navigation, stats bar, and page reachability."""

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e

PAGES = [
    ("/", "Dashboard"),
    ("/actions", "Actions"),
    ("/emails", "Emails"),
    ("/insights", "Insights"),
    ("/analytics", "Analytics"),
    ("/settings", "Settings"),
]


def test_nav_active_link_highlighting(page: Page):
    """Each page should highlight its nav link as active."""
    for path, label in PAGES:
        page.goto(path)
        # The JS in base.html adds class 'active' to the matching nav link
        active_link = page.locator(".nav-links a.active")
        expect(active_link).to_have_count(1)
        expect(active_link).to_contain_text(label)


def test_global_stats_bar_populates(page: Page, api):
    """Stats bar should show real numbers after seeding data."""
    from tests.e2e.conftest import make_action, make_email

    eid = make_email(api)
    make_action(api, eid, priority="high")
    make_action(api, eid, priority="medium")
    make_action(api, eid, priority="low")

    page.goto("/")
    # Wait for JS to fetch /api/stats and populate
    page.wait_for_function(
        "document.querySelector('#stat-todo-high')?.textContent?.trim() !== '--'"
    )
    expect(page.locator("#stat-todo-high")).to_have_text("1")
    expect(page.locator("#stat-todo-med")).to_have_text("1")
    expect(page.locator("#stat-todo-low")).to_have_text("1")


def test_all_pages_return_200(page: Page):
    """Every main page should load without errors."""
    for path, _ in PAGES:
        resp = page.goto(path)
        assert resp.status == 200, f"{path} returned {resp.status}"
        # No server error pages
        expect(page.locator("body")).not_to_contain_text("Internal Server Error")
