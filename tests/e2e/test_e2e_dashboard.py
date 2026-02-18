"""E2E tests for the dashboard page — expand/collapse, quick assign, priority change."""

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.conftest import make_action, make_assignment, make_email, make_roster_member

pytestmark = pytest.mark.e2e


def test_dashboard_loads_with_stats(page: Page, api):
    """Dashboard should show priority section cards when data exists."""
    eid = make_email(api)
    make_action(api, eid, priority="high")
    make_action(api, eid, priority="medium")
    make_action(api, eid, priority="low")

    page.goto("/")
    expect(page.locator("body")).to_contain_text("High Priority")
    expect(page.locator("body")).to_contain_text("Medium Priority")
    expect(page.locator("body")).to_contain_text("Low Priority")


def test_dashboard_overdue_expand_collapse(page: Page, api):
    """BUG REGRESSION: Overdue section must show 'Show N more' when >5 items."""
    eid = make_email(api)
    # Create 7 overdue high-priority actions
    for i in range(7):
        make_action(api, eid, priority="high", title=f"Overdue task {i+1}",
                    due_date="2026-02-10T00:00:00")

    page.goto("/")

    # The overdue section should exist
    expect(page.locator("text=Needs Immediate Attention")).to_be_visible()

    # The expand button must be present
    expand_btn = page.locator("#btn-overdue-expand")
    expect(expand_btn).to_be_visible()
    expect(expand_btn).to_contain_text("Show 2 more")

    # Extra rows should be hidden
    hidden_rows = page.locator(".overdue-extra")
    expect(hidden_rows).to_have_count(2)
    for i in range(2):
        expect(hidden_rows.nth(i)).to_be_hidden()

    # Click expand
    expand_btn.click()
    for i in range(2):
        expect(hidden_rows.nth(i)).to_be_visible()
    expect(expand_btn).to_contain_text("Show less")

    # Click collapse
    expand_btn.click()
    for i in range(2):
        expect(hidden_rows.nth(i)).to_be_hidden()


def test_dashboard_high_priority_expand_collapse(page: Page, api):
    """BUG REGRESSION: High priority section must show 'Show N more' when >5 items."""
    eid = make_email(api)
    # Create 7 high-priority actions (no due date = not overdue, so they appear in HP section)
    for i in range(7):
        make_action(api, eid, priority="high", title=f"HP task {i+1}")

    page.goto("/")

    expand_btn = page.locator("#btn-hp-expand")
    expect(expand_btn).to_be_visible()
    expect(expand_btn).to_contain_text("Show 2 more")

    hidden_rows = page.locator(".hp-extra")
    expect(hidden_rows).to_have_count(2)
    for i in range(2):
        expect(hidden_rows.nth(i)).to_be_hidden()

    expand_btn.click()
    for i in range(2):
        expect(hidden_rows.nth(i)).to_be_visible()

    expand_btn.click()
    for i in range(2):
        expect(hidden_rows.nth(i)).to_be_hidden()


def test_dashboard_medium_expand_collapse(page: Page, api):
    """Medium section should show expand when >3 items (threshold is 3)."""
    eid = make_email(api)
    for i in range(5):
        make_action(api, eid, priority="medium", title=f"Med task {i+1}")

    page.goto("/")

    expand_btn = page.locator("#btn-med-expand")
    expect(expand_btn).to_be_visible()
    expect(expand_btn).to_contain_text("Show 2 more")

    hidden = page.locator(".med-extra")
    expect(hidden).to_have_count(2)

    expand_btn.click()
    for i in range(2):
        expect(hidden.nth(i)).to_be_visible()


def test_dashboard_low_expand_collapse(page: Page, api):
    """Low section should show expand when >3 items."""
    eid = make_email(api)
    for i in range(5):
        make_action(api, eid, priority="low", title=f"Low task {i+1}")

    page.goto("/")

    expand_btn = page.locator("#btn-low-expand")
    expect(expand_btn).to_be_visible()

    hidden = page.locator(".low-extra")
    expect(hidden).to_have_count(2)


def test_dashboard_quick_assign_ajax(page: Page, api):
    """Quick assign dropdown + button should persist assignment via AJAX."""
    eid = make_email(api)
    aid = make_action(api, eid, priority="high", title="Assign me")
    make_roster_member(api, first_name="Alice", last_name="Smith", email="alice@test.com")

    page.goto("/")

    # Select the roster member from the dropdown
    sel = page.locator(f"#sel-{aid}")
    sel.select_option(label="Smith, Alice")

    # Click the Assign button next to it
    assign_btn = sel.locator("xpath=following-sibling::button")
    assign_btn.click()

    # Wait for AJAX response — button text changes to include checkmark
    assign_btn.wait_for(state="visible")
    page.wait_for_timeout(1000)

    # Verify via API
    result = api.query_assignment(aid)
    assert result["found"] is True
    assert "Smith" in result["assigned_to"] or "Alice" in result["assigned_to"]


def test_dashboard_change_priority_ajax(page: Page, api):
    """Changing priority via inline dropdown should persist via AJAX."""
    eid = make_email(api)
    aid = make_action(api, eid, priority="high", title="Reprioritize me")

    page.goto("/")

    # Find the priority select in the high-priority section for this action
    row = page.locator(f"tr[onclick*='/actions/{aid}']")
    priority_sel = row.locator("select").first
    priority_sel.select_option("low")

    page.wait_for_timeout(1000)

    # Verify via API
    result = api.query_action(aid)
    assert result["priority"] == "low"
