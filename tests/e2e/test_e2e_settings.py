"""E2E tests for the Settings page — tabs, forms, roster, categories, prompt, KB."""

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.conftest import make_roster_member

pytestmark = pytest.mark.e2e

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def test_settings_tab_switching(page: Page, api):
    """Clicking tab buttons should show/hide the correct panes."""
    page.goto("/settings")

    # Priority tab should be visible by default
    expect(page.locator("#pane-priority")).to_be_visible()

    # Switch to roster tab
    page.click("button:has-text('Program Roster')")
    expect(page.locator("#pane-roster")).to_be_visible()
    expect(page.locator("#pane-priority")).to_be_hidden()

    # Switch to categories tab
    page.click("button:has-text('Categories')")
    expect(page.locator("#pane-categories")).to_be_visible()
    expect(page.locator("#pane-roster")).to_be_hidden()

    # Switch to prompt tab
    page.click("button:has-text('Insights Prompt')")
    expect(page.locator("#pane-prompt")).to_be_visible()

    # Switch to KB tab
    page.click("button:has-text('Knowledge Base')")
    expect(page.locator("#pane-kb")).to_be_visible()


def test_settings_save_priority_rules(page: Page, api):
    """Saving settings should persist and show success message."""
    page.goto("/settings")

    page.fill("input[name='program_name']", "E2E Test Program")
    page.select_option("select[name='priority_default']", "low")
    page.fill("input[name='priority_days_threshold']", "10")
    page.click("button:has-text('Save Settings')")

    page.wait_for_url("**/settings**")
    # Verify values persisted after reload
    page.goto("/settings")
    expect(page.locator("input[name='program_name']")).to_have_value("E2E Test Program")


def test_settings_roster_add_member(page: Page, api):
    """Adding a roster member via the form should show them in the table."""
    page.goto("/settings")
    page.click("button:has-text('Program Roster')")

    page.click("button:has-text('Add Member')")
    page.fill("input[name='first_name']", "Test")
    page.fill("input[name='last_name']", "Person")
    page.fill("input[name='email']", "test.person@example.com")
    page.click("#pane-roster button:has-text('Add'):not(:has-text('Add Member'))")

    page.wait_for_url("**/settings**")
    page.click("button:has-text('Program Roster')")
    expect(page.locator("#pane-roster")).to_contain_text("Person")
    assert api.query_roster_count() == 1


def test_settings_roster_delete_member(page: Page, api):
    """Deleting a roster member should remove them from the table."""
    make_roster_member(api, first_name="Delete", last_name="Me", email="delete@test.com")

    page.goto("/settings")
    page.click("button:has-text('Program Roster')")

    page.on("dialog", lambda dialog: dialog.accept())
    # Click the delete button (✕) in the roster table
    page.locator("#pane-roster .roster-delete-btn, #pane-roster button:has-text('✕')").first.click()

    page.wait_for_url("**/settings**")
    assert api.query_roster_count() == 0


def test_settings_categories_add_remove(page: Page, api):
    """Adding and removing a category should work correctly."""
    page.goto("/settings")
    page.click("button:has-text('Categories')")

    # Add a category
    page.click("button:has-text('Add Category')")
    page.fill("#pane-categories input[name='name']", "E2ETestCat")
    page.click("#pane-categories button:has-text('Add'):not(:has-text('Add Category'))")
    page.wait_for_url("**/settings**")

    page.click("button:has-text('Categories')")
    expect(page.locator("#pane-categories")).to_contain_text("E2ETestCat")

    # Remove the category
    page.on("dialog", lambda dialog: dialog.accept())
    page.locator("#pane-categories button:has-text('Remove')").last.click()
    page.wait_for_url("**/settings**")


def test_settings_insights_prompt_save(page: Page, api):
    """Saving a custom insights prompt should persist."""
    page.goto("/settings")
    page.click("button:has-text('Insights Prompt')")

    prompt_area = page.locator("textarea[name='insights_prompt']")
    prompt_area.fill("Custom E2E test prompt with {action_details}")
    page.click("#pane-prompt button:has-text('Save Prompt')")

    page.wait_for_url("**/settings**")
    page.click("button:has-text('Insights Prompt')")
    expect(page.locator("textarea[name='insights_prompt']")).to_contain_text("Custom E2E test prompt")


def test_settings_insights_prompt_reset(page: Page, api):
    """Resetting the prompt should restore the default."""
    page.goto("/settings")
    page.click("button:has-text('Insights Prompt')")

    # Save a custom prompt first
    prompt_area = page.locator("textarea[name='insights_prompt']")
    prompt_area.fill("Temporary custom prompt")
    page.click("#pane-prompt button:has-text('Save Prompt')")
    page.wait_for_url("**/settings**")

    # Now reset
    page.click("button:has-text('Insights Prompt')")
    page.on("dialog", lambda dialog: dialog.accept())
    page.click("button:has-text('Reset to Default')")
    page.wait_for_url("**/settings**")

    page.click("button:has-text('Insights Prompt')")
    # Default prompt contains the standard analysis areas
    expect(page.locator("textarea[name='insights_prompt']")).to_contain_text("SOW Alignment")
