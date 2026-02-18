"""E2E tests for the Actions list page — filters, search, quick assign, pagination."""

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.conftest import make_action, make_assignment, make_email, make_roster_member

pytestmark = pytest.mark.e2e


def test_actions_filter_by_priority(page: Page, api):
    """Filtering by priority should show only matching actions."""
    eid = make_email(api)
    make_action(api, eid, priority="high", title="High task")
    make_action(api, eid, priority="medium", title="Medium task")
    make_action(api, eid, priority="low", title="Low task")

    page.goto("/actions")
    page.select_option("select[name='priority']", "high")
    page.click("button:has-text('Apply Filters')")

    expect(page.locator("body")).to_contain_text("High task")
    expect(page.locator("body")).not_to_contain_text("Medium task")
    expect(page.locator("body")).not_to_contain_text("Low task")


def test_actions_filter_by_status(page: Page, api):
    """Filtering by assignment status should show only matching actions."""
    eid = make_email(api)
    aid1 = make_action(api, eid, title="Unassigned task")
    aid2 = make_action(api, eid, title="Assigned task")
    make_assignment(api, aid2, assigned_to="Bob Test")

    page.goto("/actions")
    page.select_option("select[name='assigned']", "false")
    page.click("button:has-text('Apply Filters')")

    expect(page.locator("body")).to_contain_text("Unassigned task")
    expect(page.locator("body")).not_to_contain_text("Assigned task")


def test_actions_search_filter(page: Page, api):
    """Search should filter actions by title text."""
    eid = make_email(api)
    make_action(api, eid, title="Fix the SSL certificate")
    make_action(api, eid, title="Update documentation")

    page.goto("/actions")
    page.fill("input[name='search']", "SSL")
    page.click("button:has-text('Apply Filters')")

    expect(page.locator("body")).to_contain_text("SSL certificate")
    expect(page.locator("body")).not_to_contain_text("Update documentation")


def test_actions_row_click_navigates(page: Page, api):
    """Clicking an action row cell should navigate to the detail page."""
    eid = make_email(api)
    aid = make_action(api, eid, title="Clickable action")

    page.goto("/actions")
    # onclick is on individual <td> cells, not <tr>
    page.locator(f"td[onclick*='/actions/{aid}']").first.click()
    page.wait_for_url(f"**/actions/{aid}")
    expect(page.locator("body")).to_contain_text("Clickable action")


def test_actions_quick_assign_inline(page: Page, api):
    """Quick assign from the actions list should work via AJAX."""
    eid = make_email(api)
    aid = make_action(api, eid, title="Quick assign target")
    make_roster_member(api, first_name="Jane", last_name="Doe", email="jane@test.com")

    page.goto("/actions")
    # The quick assign form is in the last <td> of the row containing this action
    # Find the row by looking for a td with onclick pointing to this action
    row = page.locator(f"td[onclick*='/actions/{aid}']").first.locator("xpath=ancestor::tr")
    row.locator("select[name='assigned_to']").select_option(label="Doe, Jane")
    row.locator("button:has-text('Assign'), button:has-text('Re-assign')").click()
    page.wait_for_timeout(1000)

    result = api.query_assignment(aid)
    assert result["found"] is True


def test_actions_pagination(page: Page, api):
    """More than 50 actions should show pagination controls."""
    eid = make_email(api)
    for i in range(55):
        make_action(api, eid, title=f"Paginated action {i+1}")

    page.goto("/actions")
    expect(page.locator("body")).to_contain_text("Next")
    page.click("a:has-text('Next')")
    page.wait_for_url("**/actions?page=2**")
    expect(page.locator("body")).to_contain_text("Paginated action")
