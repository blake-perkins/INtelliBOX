"""E2E tests for the Action detail page — edit, complete, reopen, delete."""

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.conftest import (
    make_action,
    make_assignment,
    make_email,
    make_knowledge_doc,
    make_roster_member,
)

pytestmark = pytest.mark.e2e


def test_action_edit_form_saves(page: Page, api):
    """Editing action fields should persist changes."""
    eid = make_email(api)
    aid = make_action(api, eid, title="Original title", priority="medium")
    make_roster_member(api, first_name="Bob", last_name="Builder", email="bob@test.com")

    page.goto(f"/actions/{aid}")
    page.fill("input[name='title']", "Updated title")
    page.fill("textarea[name='description']", "New description")
    page.select_option("select[name='priority']", "high")
    page.fill("input[name='due_date']", "2026-03-15")
    page.select_option("select[name='category']", "RFI")
    page.select_option("select[name='assigned_to']", label="Builder, Bob")
    page.click("button:has-text('Save Changes')")

    page.wait_for_url(f"**/actions/{aid}")
    result = api.query_action(aid)
    assert result["title"] == "Updated title"
    assert result["priority"] == "high"
    assert result["category"] == "RFI"


def test_action_edit_clear_optional_fields(page: Page, api):
    """Clearing optional fields should save them as empty/null."""
    eid = make_email(api)
    aid = make_action(api, eid, title="Has due date", due_date="2026-03-01T00:00:00")

    page.goto(f"/actions/{aid}")
    page.fill("input[name='due_date']", "")
    page.click("button:has-text('Save Changes')")
    page.wait_for_url(f"**/actions/{aid}")

    result = api.query_action(aid)
    assert result["due_date"] is None


def test_action_mark_complete(page: Page, api):
    """Marking an action complete should change its status."""
    eid = make_email(api)
    aid = make_action(api, eid, title="Complete me")
    make_assignment(api, aid, assigned_to="Alice Johnson", status="assigned")

    page.goto(f"/actions/{aid}")
    page.on("dialog", lambda dialog: dialog.accept())
    page.click("button:has-text('Mark Complete')")
    page.wait_for_url(f"**/actions/{aid}")

    result = api.query_assignment(aid)
    assert result["status"] == "completed"


def test_action_reopen_after_complete(page: Page, api):
    """Reopening a completed action should change status back to assigned."""
    eid = make_email(api)
    aid = make_action(api, eid, title="Reopen me")
    make_assignment(api, aid, assigned_to="Alice Johnson", status="completed")

    page.goto(f"/actions/{aid}")
    expect(page.locator("body")).to_contain_text("COMPLETED")
    page.click("button:has-text('Reopen')")
    page.wait_for_url(f"**/actions/{aid}")

    result = api.query_assignment(aid)
    assert result["status"] == "assigned"


def test_action_delete_with_confirm(page: Page, api):
    """Deleting an action should remove it after confirmation."""
    eid = make_email(api)
    aid = make_action(api, eid, title="Delete me")

    page.goto(f"/actions/{aid}")

    # Accept the confirmation dialog
    page.on("dialog", lambda dialog: dialog.accept())

    # Open the details/danger zone section if collapsed
    details = page.locator("details")
    if details.count() > 0:
        details.last.locator("summary").click()

    page.click("button:has-text('Delete Action')")
    page.wait_for_url("**/emails/**")

    result = api.query_action(aid)
    assert result["found"] is False


def test_action_delete_cancel(page: Page, api):
    """Dismissing the delete confirmation should keep the action."""
    eid = make_email(api)
    aid = make_action(api, eid, title="Dont delete me")

    page.goto(f"/actions/{aid}")
    page.on("dialog", lambda dialog: dialog.dismiss())

    details = page.locator("details")
    if details.count() > 0:
        details.last.locator("summary").click()

    page.click("button:has-text('Delete Action')")
    page.wait_for_timeout(500)

    result = api.query_action(aid)
    assert result["found"] is True


def test_action_detail_shows_related_actions(page: Page, api):
    """The detail page should show other actions from the same email."""
    eid = make_email(api)
    aid1 = make_action(api, eid, title="First action from email")
    aid2 = make_action(api, eid, title="Second action from email")

    page.goto(f"/actions/{aid1}")
    expect(page.locator("body")).to_contain_text("Second action from email")


def test_action_assignee_dropdown_vs_cta(page: Page, api):
    """No roster = 'Add Team Members' CTA. With roster = assignee dropdown."""
    eid = make_email(api)
    aid = make_action(api, eid, title="Check roster display")

    # No roster members yet
    page.goto(f"/actions/{aid}")
    expect(page.locator("body")).to_contain_text("Add Team Members")

    # Add a roster member and reload
    make_roster_member(api, first_name="Tom", last_name="Lee", email="tom@test.com")
    page.reload()
    expect(page.locator("select[name='assigned_to']")).to_be_visible()
