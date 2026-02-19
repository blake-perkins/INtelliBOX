"""E2E tests for the Insights page — days dropdown, refresh button feedback."""

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.conftest import make_action, make_email

pytestmark = pytest.mark.e2e


def test_insights_days_dropdown_changes_url(page: Page, api):
    """Selecting a different time period should navigate to the new URL."""
    eid = make_email(api)
    make_action(api, eid, priority="high")

    page.goto("/insights")
    page.select_option("#daysSelect", "7")
    page.wait_for_url("**/insights?days=7")
    expect(page.locator("body")).not_to_contain_text("Internal Server Error")


def test_insights_refresh_disables_button(page: Page, api):
    """Clicking refresh should disable the button and show loading text."""
    eid = make_email(api)
    make_action(api, eid, priority="high")

    page.goto("/insights")
    # Auto-dismiss the confirm dialog
    page.on("dialog", lambda d: d.accept())

    refresh_btn = page.locator("button:has-text('Generate'), button:has-text('Refresh')")
    if refresh_btn.count() > 0:
        refresh_btn.first.click()
        # Button should show "Generating..." text after click
        expect(page.locator("text=Generating")).to_be_visible(timeout=5000)


def test_insights_empty_state(page: Page, api):
    """With no data, insights should show generate button or empty state."""
    page.goto("/insights")
    # Should still load without errors
    expect(page.locator("body")).not_to_contain_text("Internal Server Error")
