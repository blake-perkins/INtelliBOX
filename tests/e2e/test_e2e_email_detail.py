"""E2E tests for the Email detail page — tab toggle, action list, create action."""

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.conftest import make_action, make_email

pytestmark = pytest.mark.e2e


def test_email_detail_tab_toggle(page: Page, api):
    """HTML/Plain Text tabs should toggle visibility."""
    eid = make_email(api, body_text="Plain text body here", body_html="<p>HTML body here</p>")

    page.goto(f"/emails/{eid}")

    # HTML tab should be active by default (or plain text — check which)
    text_tab = page.locator("#tab-text")
    html_tab = page.locator("#tab-html")

    # Click Plain Text
    text_tab.click()
    text_body = page.locator("#text-body")
    expect(text_body).to_be_visible()

    # Click HTML View
    html_tab.click()
    html_body = page.locator("#html-body")
    expect(html_body).to_be_visible()


def test_email_detail_shows_actions(page: Page, api):
    """Email detail should list extracted actions."""
    eid = make_email(api, subject="Email with actions")
    make_action(api, eid, title="First action")
    make_action(api, eid, title="Second action")

    page.goto(f"/emails/{eid}")
    expect(page.locator("body")).to_contain_text("First action")
    expect(page.locator("body")).to_contain_text("Second action")
    expect(page.locator("body")).to_contain_text("(2)")


def test_email_detail_create_action_button(page: Page, api):
    """The '+ Create Action' button should navigate to the create form."""
    eid = make_email(api)

    page.goto(f"/emails/{eid}")
    page.click("a:has-text('Create Action')")
    page.wait_for_url(f"**/emails/{eid}/actions/new")
    expect(page.locator("body")).to_contain_text("Create Action")

    # Fill and submit the form
    page.fill("input[name='title']", "Manually created action")
    page.click("button:has-text('Create Action')")
    page.wait_for_url("**/actions/**")
    expect(page.locator("body")).to_contain_text("Manually created action")


def test_email_detail_no_actions_empty_state(page: Page, api):
    """Email with no extracted actions should show empty state."""
    eid = make_email(api)

    page.goto(f"/emails/{eid}")
    expect(page.locator("body")).to_contain_text("No actions extracted")
