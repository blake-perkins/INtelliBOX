"""E2E tests for the Emails page — upload, filters, empty-days regression."""

import pytest
from pathlib import Path
from playwright.sync_api import Page, expect

from tests.e2e.conftest import make_email

pytestmark = pytest.mark.e2e

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def test_email_upload_eml_file(page: Page, api):
    """Uploading a .eml file should succeed and show a success banner."""
    eml_path = FIXTURES_DIR / "sample_emails" / "simple_rfi.eml"
    if not eml_path.exists():
        pytest.skip(f"Fixture file not found: {eml_path}")

    page.goto("/emails")
    page.set_input_files("input[type='file']", str(eml_path))
    page.click("button:has-text('Upload')")

    # Should redirect with success indicator
    page.wait_for_url("**/emails**")
    # The page should load without errors
    expect(page.locator("body")).not_to_contain_text("Internal Server Error")


def test_email_upload_invalid_extension(page: Page, api):
    """Uploading a non-.eml/.msg file should show an error."""
    # Create a temporary .txt file
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
        f.write("not an email")
        tmp_path = f.name

    page.goto("/emails")
    page.set_input_files("input[type='file']", tmp_path)
    page.click("button:has-text('Upload')")
    page.wait_for_url("**/emails**")

    # Should show error about unsupported file type
    expect(page.locator("body")).to_contain_text("Unsupported")

    import os
    os.unlink(tmp_path)


def test_email_filter_empty_days_no_crash(page: Page, api):
    """BUG REGRESSION: Submitting filters with empty 'days' should not crash.

    The browser sends ?days= (empty string) when 'All Time' is selected.
    Previously this crashed because days was typed as Optional[int] and
    int('') raises ValueError.
    """
    make_email(api, subject="Visible email")

    page.goto("/emails")
    # Leave the Date Range on "All Time" (sends days= as empty string)
    page.select_option("select[name='days']", "")
    page.click("button:has-text('Apply Filters')")

    # Page should load fine, not a 422/500
    expect(page.locator("body")).to_contain_text("Visible email")
    expect(page.locator("body")).not_to_contain_text("Internal Server Error")
    expect(page.locator("body")).not_to_contain_text("422")


def test_email_filter_by_processed_status(page: Page, api):
    """Filtering by processed status should show matching emails only."""
    make_email(api, subject="Processed email", processed=True, processed_at="2026-02-15T10:00:00")
    make_email(api, subject="Unprocessed email", processed=False, processed_at=None)

    page.goto("/emails")
    page.select_option("select[name='processed']", "true")
    page.click("button:has-text('Apply Filters')")

    expect(page.locator("body")).to_contain_text("Processed email")
    expect(page.locator("body")).not_to_contain_text("Unprocessed email")


def test_email_row_click_navigates(page: Page, api):
    """Clicking an email row should navigate to the detail page."""
    eid = make_email(api, subject="Click this email")

    page.goto("/emails")
    page.locator(f"tr[onclick*='/emails/{eid}']").click()
    page.wait_for_url(f"**/emails/{eid}")
    expect(page.locator("body")).to_contain_text("Click this email")
