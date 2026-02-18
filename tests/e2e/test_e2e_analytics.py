"""E2E tests for the Analytics page — data display and empty state."""

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.conftest import make_action, make_email, make_roster_member

pytestmark = pytest.mark.e2e


def test_analytics_loads_with_data(page: Page, api):
    """Analytics page should display system stats when data exists."""
    eid = make_email(api)
    make_action(api, eid, priority="high")
    make_action(api, eid, priority="medium")
    make_roster_member(api, first_name="Ana", last_name="Lyst", email="ana@test.com")

    page.goto("/analytics")
    expect(page.locator("body")).to_contain_text("System Analytics")
    # Should show email and action counts
    expect(page.locator("body")).to_contain_text("1")  # 1 email
    expect(page.locator("body")).to_contain_text("2")  # 2 actions


def test_analytics_loads_empty(page: Page, api):
    """Analytics page should load cleanly with no data."""
    page.goto("/analytics")
    expect(page.locator("body")).to_contain_text("System Analytics")
    expect(page.locator("body")).to_contain_text("0")
    expect(page.locator("body")).not_to_contain_text("Internal Server Error")
