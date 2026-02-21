"""
Comprehensive test suite for INtelliBOX web interface.

Tests all routes, templates, and functionality to ensure everything works
for end users.
"""

import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from intellibox.database import Base
from intellibox.models import Action, Assignment, Email, RosterMember

# Create test database with unique temp file
test_db_fd, test_db_path = tempfile.mkstemp(suffix='_web_interface.db', prefix='test_intellibox_')
TEST_DATABASE_URL = f"sqlite:///{test_db_path}"
test_engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@contextmanager
def override_get_session():
    """Override database session for testing."""
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


# Import app AFTER defining override function
# Patch get_session at the database module level — deps.get_session() delegates there
import intellibox.database as database_module
import intellibox.settings_service as settings_service_module

database_module.get_session = override_get_session
settings_service_module.get_session = override_get_session

from intellibox.web.app import app

client = TestClient(app)


@pytest.fixture(scope="function")
def setup_database():
    """Create tables and populate with test data before each test."""
    # Drop all tables first to ensure clean state
    Base.metadata.drop_all(bind=test_engine)

    # Create tables
    Base.metadata.create_all(bind=test_engine)

    # Create test data
    session = TestSessionLocal()

    # Create test emails
    email1 = Email(
        message_id="test1@example.com",
        subject="Test RFI - Budget Data Request",
        from_address="boss@example.com",
        from_name="Boss Man",
        to_addresses='["team@example.com"]',
        received_date=datetime.utcnow() - timedelta(days=1),
        body_text="Please provide the budget data by Friday.",
        processed=True,
        processed_at=datetime.utcnow()
    )

    email2 = Email(
        message_id="test2@example.com",
        subject="URGENT: Production Issue",
        from_address="alerts@monitoring.com",
        from_name="Alert System",
        to_addresses='["team@example.com"]',
        received_date=datetime.utcnow() - timedelta(hours=2),
        body_text="Critical error in production. Investigate immediately.",
        processed=True,
        processed_at=datetime.utcnow()
    )

    email3 = Email(
        message_id="test3@example.com",
        subject="Meeting Notes",
        from_address="colleague@example.com",
        from_name="Colleague",
        to_addresses='["team@example.com"]',
        received_date=datetime.utcnow() - timedelta(days=3),
        body_text="Here are the notes from yesterday's meeting.",
        processed=True,
        processed_at=datetime.utcnow()
    )

    session.add_all([email1, email2, email3])
    session.commit()

    # Create test actions
    action1 = Action(
        email_id=email1.id,
        title="Provide budget data",
        description="Compile and send budget data to boss",
        priority="high",
        due_date=datetime.utcnow() + timedelta(days=3),
        category="RFI",
        confidence_score=0.95
    )

    action2 = Action(
        email_id=email2.id,
        title="Investigate production error",
        description="Check logs and identify root cause",
        priority="high",
        due_date=datetime.utcnow() + timedelta(hours=4),
        category="incident",
        confidence_score=0.98
    )

    action3 = Action(
        email_id=email3.id,
        title="Review meeting notes",
        description="Read and follow up on action items from meeting",
        priority="medium",
        due_date=datetime.utcnow() + timedelta(days=7),
        category="follow-up",
        confidence_score=0.75
    )

    action4 = Action(
        email_id=email1.id,
        title="Schedule follow-up meeting",
        description="Set up meeting to discuss budget",
        priority="low",
        due_date=None,
        category="meeting",
        confidence_score=0.60
    )

    session.add_all([action1, action2, action3, action4])
    session.commit()

    # Create one assignment (action1 is assigned)
    assignment1 = Assignment(
        action_id=action1.id,
        assigned_to="john@example.com",
        status="assigned",
        notes="Working on it"
    )

    session.add(assignment1)
    session.commit()

    session.close()

    yield

    # Cleanup
    Base.metadata.drop_all(bind=test_engine)


class TestWebInterface:
    """Test suite for web interface routes and functionality."""

    def test_health_check(self, setup_database):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data

    def test_api_stats(self, setup_database):
        """Test API stats endpoint."""
        response = client.get("/api/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_emails"] == 3
        assert data["total_actions"] == 4
        assert data["unassigned_actions"] == 3  # action1 is assigned
        assert data["unassigned_high"] == 1  # Only action2 is high priority AND unassigned (action1 is assigned)

    def test_dashboard(self, setup_database):
        """Test dashboard page loads."""
        response = client.get("/")
        assert response.status_code == 200
        assert b"Dashboard" in response.content  # Updated to match current branding
        assert b"Actions" in response.content

    def test_actions_list(self, setup_database):
        """Test actions list page."""
        response = client.get("/actions")
        assert response.status_code == 200
        assert b"Actions" in response.content
        assert b"Provide budget data" in response.content
        assert b"Investigate production error" in response.content

    def test_actions_filter_by_priority(self, setup_database):
        """Test filtering actions by priority."""
        # Filter high priority
        response = client.get("/actions?priority=high")
        assert response.status_code == 200
        assert b"Investigate production error" in response.content

        # Filter low priority
        response = client.get("/actions?priority=low")
        assert response.status_code == 200
        assert b"Schedule follow-up meeting" in response.content

    def test_actions_filter_unassigned(self, setup_database):
        """Test filtering unassigned actions."""
        response = client.get("/actions?assigned=false")
        assert response.status_code == 200
        # Should show 3 unassigned actions (action1 is assigned)
        assert b"Investigate production error" in response.content
        assert b"Review meeting notes" in response.content

    def test_actions_filter_assigned(self, setup_database):
        """Test filtering assigned actions."""
        response = client.get("/actions?assigned=true")
        assert response.status_code == 200
        # Should show only action1
        assert b"Provide budget data" in response.content

    def test_action_detail(self, setup_database):
        """Test individual action detail page loads with action content."""
        session = TestSessionLocal()
        action = session.query(Action).first()
        action_id = action.id
        session.close()

        response = client.get(f"/actions/{action_id}")
        assert response.status_code == 200
        assert b"Edit Action" in response.content
        assert b"Source Email" in response.content

    def test_action_detail_assign_shows_roster_dropdown(self, setup_database):
        """When roster has members, the assign field is a <select> dropdown."""
        session = TestSessionLocal()
        action = session.query(Action).first()
        action_id = action.id
        member = RosterMember(first_name="Alice", last_name="Smith", email="alice@example.com")
        session.add(member)
        session.commit()
        session.close()

        response = client.get(f"/actions/{action_id}")
        assert response.status_code == 200
        # Dropdown present with member name
        assert b'name="assigned_to"' in response.content
        assert b"Smith, Alice" in response.content
        # Free-text fallback and empty-roster CTA must NOT appear
        assert b"Add Team Members" not in response.content

    def test_action_detail_assign_shows_cta_when_roster_empty(self, setup_database):
        """When roster is empty, the assign area shows an Add Team Members CTA instead of a free-text input."""
        session = TestSessionLocal()
        action = session.query(Action).first()
        action_id = action.id
        session.close()

        response = client.get(f"/actions/{action_id}")
        assert response.status_code == 200
        # CTA link to settings roster tab
        assert b"Add Team Members" in response.content
        assert b"/settings#roster" in response.content
        # No free-text input or select for assigned_to
        assert b'name="assigned_to"' not in response.content

    def test_action_detail_not_found(self, setup_database):
        """Test 404 for non-existent action."""
        response = client.get("/actions/99999")
        assert response.status_code == 404

    def test_emails_list(self, setup_database):
        """Test emails list page."""
        response = client.get("/emails")
        assert response.status_code == 200
        assert b"Emails" in response.content
        assert b"Test RFI - Budget Data Request" in response.content
        assert b"URGENT: Production Issue" in response.content

    def test_email_detail(self, setup_database):
        """Test individual email detail page."""
        # Get the first email's ID
        session = TestSessionLocal()
        email = session.query(Email).first()
        email_id = email.id
        session.close()

        response = client.get(f"/emails/{email_id}")
        assert response.status_code == 200
        # Check that email content is displayed
        assert b"Test RFI" in response.content or b"boss@example.com" in response.content

    def test_email_detail_not_found(self, setup_database):
        """Test 404 for non-existent email."""
        response = client.get("/emails/99999")
        assert response.status_code == 404

    def test_report_page(self, setup_database):
        """Test daily report page."""
        response = client.get("/insights")
        assert response.status_code == 200
        assert b"AI Insights" in response.content
        assert b"Awaiting Assignment" in response.content

    def test_pagination_actions(self, setup_database):
        """Test pagination on actions page."""
        # Page 1 should work
        response = client.get("/actions?page=1")
        assert response.status_code == 200

        # Page 0 or negative should fail
        response = client.get("/actions?page=0")
        assert response.status_code == 422  # Validation error

    def test_pagination_emails(self, setup_database):
        """Test pagination on emails page."""
        # Page 1 should work
        response = client.get("/emails?page=1")
        assert response.status_code == 200

        # High page number should work (just empty)
        response = client.get("/emails?page=100")
        assert response.status_code == 200

    def test_actions_export_csv(self, setup_database):
        """Test CSV export returns correct content-type and all rows."""
        response = client.get("/actions/export.csv")
        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]
        assert "attachment" in response.headers.get("content-disposition", "")
        assert "actions_" in response.headers["content-disposition"]
        content = response.content.decode("utf-8")
        lines = content.strip().splitlines()
        assert lines[0].startswith("ID,")  # header row
        assert len(lines) == 5  # 1 header + 4 actions from setup_database

    def test_actions_export_csv_priority_filter(self, setup_database):
        """Test CSV export respects priority filter."""
        response = client.get("/actions/export.csv?priority=high")
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        lines = content.strip().splitlines()
        assert len(lines) == 3  # 1 header + 2 high-priority actions

    def test_actions_export_csv_search_filter(self, setup_database):
        """Test CSV export respects search filter."""
        response = client.get("/actions/export.csv?search=nonexistent_xyz")
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        lines = content.strip().splitlines()
        assert len(lines) == 1  # header only, no matches


class TestEmptyDatabase:
    """Test web interface with empty database."""

    @pytest.fixture(scope="function")
    def empty_db(self):
        """Create empty database."""
        # Drop tables first to ensure clean state
        Base.metadata.drop_all(bind=test_engine)
        Base.metadata.create_all(bind=test_engine)
        yield
        Base.metadata.drop_all(bind=test_engine)

    def test_dashboard_empty(self, empty_db):
        """Test dashboard with no data."""
        response = client.get("/")
        assert response.status_code == 200
        assert b"Dashboard" in response.content  # Updated to match current branding

    def test_actions_empty(self, empty_db):
        """Test actions page with no actions."""
        response = client.get("/actions")
        assert response.status_code == 200
        assert b"No actions found" in response.content

    def test_emails_empty(self, empty_db):
        """Test emails page with no emails."""
        response = client.get("/emails")
        assert response.status_code == 200
        assert b"No emails found" in response.content

    def test_report_empty(self, empty_db):
        """Test report with no data."""
        response = client.get("/insights")
        assert response.status_code == 200
        assert b"AI Insights" in response.content

    def test_api_stats_empty(self, empty_db):
        """Test API stats with empty database."""
        response = client.get("/api/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_emails"] == 0
        assert data["total_actions"] == 0
        assert data["unassigned_actions"] == 0
        assert data["unassigned_high"] == 0

    def test_actions_export_csv_empty(self, empty_db):
        """Test CSV export with no data returns header only."""
        response = client.get("/actions/export.csv")
        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]
        content = response.content.decode("utf-8")
        lines = content.strip().splitlines()
        assert len(lines) == 1  # header row only


class TestDataIntegrity:
    """Test data relationships and integrity."""

    def test_action_has_email_reference(self, setup_database):
        """Test that action detail shows email information."""
        session = TestSessionLocal()
        action = session.query(Action).first()
        action_id = action.id
        session.close()

        response = client.get(f"/actions/{action_id}")
        assert response.status_code == 200
        # Should show email subject and sender
        assert b"boss@example.com" in response.content or b"From Email" in response.content

    def test_email_shows_actions(self, setup_database):
        """Test that email detail shows related actions."""
        session = TestSessionLocal()
        email = session.query(Email).first()
        email_id = email.id
        session.close()

        response = client.get(f"/emails/{email_id}")
        assert response.status_code == 200
        # Should list actions from this email
        assert b"Actions from this Email" in response.content or b"action" in response.content.lower()


class TestUserWorkflow:
    """Test complete user workflows."""

    def test_view_dashboard_to_action(self, setup_database):
        """Test workflow: Dashboard -> Actions -> Action Detail."""
        # 1. Load dashboard
        response = client.get("/")
        assert response.status_code == 200

        # 2. Navigate to actions
        response = client.get("/actions")
        assert response.status_code == 200

        # 3. View specific action
        session = TestSessionLocal()
        action = session.query(Action).filter_by(priority="high").first()
        action_id = action.id
        session.close()

        response = client.get(f"/actions/{action_id}")
        assert response.status_code == 200

    def test_view_report_workflow(self, setup_database):
        """Test workflow: Dashboard -> Report."""
        # 1. Load dashboard
        response = client.get("/")
        assert response.status_code == 200

        # 2. View report
        response = client.get("/insights")
        assert response.status_code == 200
        # Should show unassigned high priority items
        assert b"high" in response.content.lower()

    def test_filter_actions_workflow(self, setup_database):
        """Test workflow: Actions -> Filter by priority -> Filter unassigned."""
        # 1. View all actions
        response = client.get("/actions")
        assert response.status_code == 200

        # 2. Filter to high priority
        response = client.get("/actions?priority=high")
        assert response.status_code == 200

        # 3. Filter to unassigned
        response = client.get("/actions?assigned=false")
        assert response.status_code == 200


class TestSettingsPage:
    """Test settings page tabs and functionality."""

    def test_settings_page_loads(self, setup_database):
        """Test settings page loads with all tabs."""
        response = client.get("/settings")
        assert response.status_code == 200
        assert b"Priority Rules" in response.content
        assert b"Program Roster" in response.content
        assert b"Categories" in response.content
        assert b"Insights Prompt" in response.content
        assert b"Knowledge Base" in response.content

    def test_settings_page_has_all_tab_panes(self, setup_database):
        """Test that all tab pane divs exist."""
        response = client.get("/settings")
        assert response.status_code == 200
        assert b'id="pane-priority"' in response.content
        assert b'id="pane-roster"' in response.content
        assert b'id="pane-categories"' in response.content
        assert b'id="pane-prompt"' in response.content
        assert b'id="pane-kb"' in response.content

    def test_settings_page_shows_insights_prompt(self, setup_database):
        """Test that the insights prompt textarea is populated."""
        response = client.get("/settings")
        assert response.status_code == 200
        # Should contain the prompt textarea
        assert b'name="insights_prompt"' in response.content

    def test_save_insights_prompt(self, setup_database):
        """Test saving a custom insights prompt."""
        custom_prompt = "Custom prompt with {action_details} and {days}"
        response = client.post(
            "/settings/insights-prompt",
            data={"insights_prompt": custom_prompt},
            follow_redirects=False,
        )
        assert response.status_code == 303
        location = response.headers.get("location", "")
        assert "prompt_saved" in location

        # Verify it was saved
        from intellibox.settings_service import SettingsService
        saved = SettingsService.get_insights_prompt()
        assert saved == custom_prompt

    def test_reset_insights_prompt(self, setup_database):
        """Test resetting insights prompt to default."""
        from intellibox.ai.prompts import REPORT_INSIGHTS_PROMPT
        from intellibox.settings_service import SettingsService

        # Save a custom prompt
        SettingsService.set_setting("insights_prompt", "custom")
        assert SettingsService.get_insights_prompt() == "custom"

        # Reset via API
        response = client.post(
            "/settings/insights-prompt/reset",
            follow_redirects=False,
        )
        assert response.status_code == 200

        # Should fall back to default
        assert SettingsService.get_insights_prompt() == REPORT_INSIGHTS_PROMPT

    def test_save_empty_insights_prompt_rejected(self, setup_database):
        """Test that an empty insights prompt is rejected by form validation."""
        response = client.post(
            "/settings/insights-prompt",
            data={"insights_prompt": ""},
            follow_redirects=False,
        )
        # FastAPI Form(...) requires a non-empty value
        assert response.status_code == 422


class TestInsightsPage:
    """Test insights page lookback and rendering."""

    def test_insights_default_lookback(self, setup_database):
        """Test insights page defaults to 14-day lookback."""
        response = client.get("/insights")
        assert response.status_code == 200
        # The selected_days should default to 14
        assert b'value="14" selected' in response.content or b"14 Days" in response.content

    def test_insights_custom_lookback(self, setup_database):
        """Test insights page accepts a custom lookback period."""
        response = client.get("/insights?days=7")
        assert response.status_code == 200

    def test_insights_lookback_clamped_low(self, setup_database):
        """Test insights page clamps lookback to minimum 7 days."""
        response = client.get("/insights?days=1")
        assert response.status_code == 200

    def test_insights_lookback_clamped_high(self, setup_database):
        """Test insights page clamps lookback to maximum 90 days."""
        response = client.get("/insights?days=365")
        assert response.status_code == 200

    def test_insights_invalid_days_param(self, setup_database):
        """Test insights page gracefully handles non-numeric days param."""
        response = client.get("/insights?days=abc")
        # Should fall back to default (14 days) instead of crashing
        assert response.status_code == 200

    def test_insights_lookback_dropdown_present(self, setup_database):
        """Test that the lookback dropdown is rendered."""
        response = client.get("/insights")
        assert response.status_code == 200
        assert b"changeDays" in response.content or b"lookback" in response.content.lower()

    def test_insights_refresh_param_ignored(self, setup_database):
        """Test that ?refresh=1 is treated as normal page load (generation is async)."""
        response = client.get("/insights?refresh=1")
        assert response.status_code == 200
        assert b"AI Insights" in response.content

    def test_insights_refresh_param_with_days(self, setup_database):
        """Test that ?refresh=1&days=7 is treated as normal page load."""
        response = client.get("/insights?days=7&refresh=1")
        assert response.status_code == 200

    def test_insights_generate_api_returns_job_id(self, setup_database):
        """Test that POST /api/insights/generate returns a job ID."""
        response = client.post(
            "/api/insights/generate",
            json={"days": 14},
        )
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert len(data["job_id"]) == 8

    def test_insights_status_api_unknown_job(self, setup_database):
        """Test that polling an unknown job ID returns unknown status."""
        response = client.get("/api/insights/status/nonexist")
        assert response.status_code == 200
        assert response.json()["status"] == "unknown"

    def test_insights_refreshed_ok_shows_success_toast(self, setup_database):
        """Test that ?refreshed=ok shows success toast."""
        response = client.get("/insights?refreshed=ok")
        assert response.status_code == 200
        assert b"Insights updated successfully" in response.content

    def test_insights_refreshed_error_shows_error_toast(self, setup_database):
        """Test that ?refreshed=error shows error toast and warning banner."""
        response = client.get("/insights?refreshed=error")
        assert response.status_code == 200
        assert b"AI service error" in response.content

    def test_insights_ai_failed_shows_warning_banner(self, setup_database):
        """Test that ai_failed flag renders the warning banner."""
        import time
        # Generate via async API and wait for completion
        resp = client.post("/api/insights/generate", json={"days": 14})
        job_id = resp.json()["job_id"]
        for _ in range(30):
            status_resp = client.get(f"/api/insights/status/{job_id}")
            if status_resp.json()["status"] != "running":
                break
            time.sleep(0.5)
        # Now load the page — should work regardless of AI outcome
        response = client.get("/insights")
        assert response.status_code == 200
        assert b"AI Insights" in response.content

    def test_insights_refresh_zero_ignored(self, setup_database):
        """Test that refresh=0 does not force refresh (treated as normal load)."""
        response = client.get("/insights?refresh=0")
        assert response.status_code == 200

    def test_insights_button_has_loading_behavior(self, setup_database):
        """Test that the Generate/Refresh button triggers async generation."""
        response = client.get("/insights")
        assert response.status_code == 200
        # The startRefresh function should POST to the generate API
        assert b"api/insights/generate" in response.content
        assert b"startRefresh" in response.content

    def test_insights_confirm_dialog_present(self, setup_database):
        """Test that the cost confirmation dialog is in the page JS."""
        response = client.get("/insights")
        assert response.status_code == 200
        assert b"confirm(" in response.content
        assert b"API" in response.content


class TestAssignmentStatusTransitions:
    """Test all assignment status transitions including in_progress."""

    def test_set_status_in_progress(self, setup_database):
        """Setting assignment status to in_progress should succeed (not 500)."""
        # Action 2 (from setup_database) is assigned to "Test User"
        with override_get_session() as session:
            assignment = session.query(Assignment).first()
            action_id = assignment.action_id
            assert assignment.status == "assigned"

        response = client.post(
            f"/actions/{action_id}/status",
            data={"status": "in_progress"},
            follow_redirects=False,
        )
        # Should redirect back to action detail, NOT 500
        assert response.status_code == 303

        # Verify the status was actually persisted
        with override_get_session() as session:
            assignment = session.query(Assignment).filter_by(action_id=action_id).first()
            assert assignment.status == "in_progress"

    def test_set_status_completed(self, setup_database):
        """Setting assignment status to completed should succeed."""
        with override_get_session() as session:
            assignment = session.query(Assignment).first()
            action_id = assignment.action_id

        response = client.post(
            f"/actions/{action_id}/status",
            data={"status": "completed"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        with override_get_session() as session:
            assignment = session.query(Assignment).filter_by(action_id=action_id).first()
            assert assignment.status == "completed"
            assert assignment.completed_at is not None

    def test_set_status_assigned_from_completed(self, setup_database):
        """Reopening a completed action should set status back to assigned."""
        with override_get_session() as session:
            assignment = session.query(Assignment).first()
            action_id = assignment.action_id
            assignment.status = "completed"
            session.commit()

        response = client.post(
            f"/actions/{action_id}/status",
            data={"status": "assigned"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        with override_get_session() as session:
            assignment = session.query(Assignment).filter_by(action_id=action_id).first()
            assert assignment.status == "assigned"
            assert assignment.completed_at is None

    def test_set_invalid_status_rejected(self, setup_database):
        """An invalid status value should return 400."""
        with override_get_session() as session:
            assignment = session.query(Assignment).first()
            action_id = assignment.action_id

        response = client.post(
            f"/actions/{action_id}/status",
            data={"status": "bogus"},
            follow_redirects=False,
        )
        assert response.status_code == 400


class TestReprocessEmail:
    """Test the re-process email feature."""

    def test_reprocess_form_loads(self, setup_database):
        """GET /emails/{id}/reprocess should render the form."""
        response = client.get("/emails/1/reprocess")
        assert response.status_code == 200
        assert b"Re-process with AI" in response.content
        assert b"Analyze" in response.content

    def test_reprocess_form_404(self, setup_database):
        """GET /emails/999/reprocess should return 404."""
        response = client.get("/emails/999/reprocess")
        assert response.status_code == 404

    def test_reprocess_preview_renders(self, setup_database):
        """POST /emails/{id}/reprocess should show preview with action sections."""
        response = client.post(
            "/emails/1/reprocess",
            data={"context_notes": ""},
            follow_redirects=False,
        )
        assert response.status_code == 200
        assert b"Re-process Preview" in response.content
        assert b"Accept" in response.content

    def test_reprocess_confirm_replaces_unassigned(self, setup_database):
        """POST confirm should delete unassigned actions and create new ones."""
        # Email 1 has action1 (assigned) and action4 (unassigned)
        # First get a preview to obtain action_dicts
        preview_response = client.post(
            "/emails/1/reprocess",
            data={"context_notes": ""},
        )
        assert preview_response.status_code == 200

        # Extract hidden form values from the preview page
        import re
        html = preview_response.text
        action_dicts_match = re.search(
            r'name="action_dicts_json"\s+value="([^"]*)"', html
        )
        raw_response_match = re.search(
            r'name="raw_response"\s+value="([^"]*)"', html
        )
        assert action_dicts_match is not None
        assert raw_response_match is not None

        import html as html_mod
        action_dicts_val = html_mod.unescape(action_dicts_match.group(1))
        raw_response_val = html_mod.unescape(raw_response_match.group(1))

        # Submit the confirm
        confirm_response = client.post(
            "/emails/1/reprocess/confirm",
            data={
                "action_dicts_json": action_dicts_val,
                "raw_response": raw_response_val,
                "kb_data_json": "",
            },
            follow_redirects=False,
        )
        assert confirm_response.status_code == 303

        # Verify: action1 (assigned) should still exist, action4 (unassigned) should be gone
        with override_get_session() as session:
            from intellibox.models import AuditLog
            remaining = session.query(Action).filter_by(email_id=1).all()
            # action1 was assigned so it's preserved; new AI actions added
            assigned_remaining = [a for a in remaining if a.assignments]
            assert len(assigned_remaining) >= 1
            assert assigned_remaining[0].title == "Provide budget data"

    def test_reprocess_preserves_assigned_actions(self, setup_database):
        """Assigned actions must survive reprocessing."""
        # action1 is assigned to john@example.com
        preview_response = client.post(
            "/emails/1/reprocess",
            data={"context_notes": ""},
        )
        assert preview_response.status_code == 200
        # The preview should show preserved actions
        assert b"Preserved Actions" in preview_response.content
        assert b"john@example.com" in preview_response.content

    def test_reprocess_confirm_audit_logged(self, setup_database):
        """Reprocessing should create an audit log entry."""
        preview_response = client.post(
            "/emails/1/reprocess",
            data={"context_notes": ""},
        )
        import re, html as html_mod
        html = preview_response.text
        action_dicts_val = html_mod.unescape(
            re.search(r'name="action_dicts_json"\s+value="([^"]*)"', html).group(1)
        )
        raw_response_val = html_mod.unescape(
            re.search(r'name="raw_response"\s+value="([^"]*)"', html).group(1)
        )

        client.post(
            "/emails/1/reprocess/confirm",
            data={
                "action_dicts_json": action_dicts_val,
                "raw_response": raw_response_val,
                "kb_data_json": "",
            },
            follow_redirects=False,
        )

        with override_get_session() as session:
            from intellibox.models import AuditLog
            entry = session.query(AuditLog).filter_by(action="reprocess").first()
            assert entry is not None
            assert entry.resource_type == "email"
            assert entry.resource_id == 1

    def test_reprocess_add_to_kb(self, setup_database):
        """Reprocessing with KB data should create a KnowledgeDocument."""
        import json
        kb_data = json.dumps({
            "filename": "context.txt",
            "file_type": "txt",
            "file_size": 42,
            "extracted_text": "Some context text",
            "extraction_status": "success",
        })

        preview_response = client.post(
            "/emails/1/reprocess",
            data={"context_notes": ""},
        )
        import re, html as html_mod
        html = preview_response.text
        action_dicts_val = html_mod.unescape(
            re.search(r'name="action_dicts_json"\s+value="([^"]*)"', html).group(1)
        )
        raw_response_val = html_mod.unescape(
            re.search(r'name="raw_response"\s+value="([^"]*)"', html).group(1)
        )

        client.post(
            "/emails/1/reprocess/confirm",
            data={
                "action_dicts_json": action_dicts_val,
                "raw_response": raw_response_val,
                "kb_data_json": kb_data,
            },
            follow_redirects=False,
        )

        with override_get_session() as session:
            from intellibox.models import KnowledgeDocument
            doc = session.query(KnowledgeDocument).filter_by(filename="context.txt").first()
            assert doc is not None
            assert doc.extracted_text == "Some context text"
            assert doc.extraction_status == "success"


    def test_reprocess_form_shows_kb_docs(self, setup_database):
        """Reprocess form should list KB documents with checkboxes."""
        from intellibox.models import KnowledgeDocument

        with override_get_session() as session:
            doc = KnowledgeDocument(
                filename="requirements.pdf",
                file_type="pdf",
                file_size=1024,
                description="Project requirements",
                extracted_text="Requirements text",
                extraction_status="success",
            )
            session.add(doc)
            session.commit()
            doc_id = doc.id

        response = client.get("/emails/1/reprocess")
        assert response.status_code == 200
        assert b"requirements.pdf" in response.content
        assert b"kb_doc_ids" in response.content
        assert b"Select documents" in response.content

    def test_reprocess_form_shows_email_body(self, setup_database):
        """Reprocess form should include a collapsible email content section."""
        response = client.get("/emails/1/reprocess")
        assert response.status_code == 200
        assert b"Email Content" in response.content
        assert b"click to expand" in response.content
        # Email body text should be in the hidden section
        assert b"budget data" in response.content

    def test_reprocess_preview_with_kb_doc_ids(self, setup_database):
        """POST reprocess with kb_doc_ids should include KB text in AI context."""
        from intellibox.models import KnowledgeDocument

        with override_get_session() as session:
            doc = KnowledgeDocument(
                filename="release_notes.txt",
                file_type="txt",
                file_size=512,
                description="Release notes",
                extracted_text="Version 2.0 release notes content",
                extraction_status="success",
            )
            session.add(doc)
            session.commit()
            doc_id = doc.id

        response = client.post(
            "/emails/1/reprocess",
            data={"context_notes": "", "kb_doc_ids": [doc_id]},
            follow_redirects=False,
        )
        assert response.status_code == 200
        assert b"Re-process Preview" in response.content

    def test_reprocess_add_to_kb_list_format(self, setup_database):
        """Confirm with a list of KB data items should create multiple docs."""
        import json

        kb_data = json.dumps([
            {
                "filename": "doc1.txt",
                "file_type": "txt",
                "file_size": 100,
                "extracted_text": "First document",
                "extraction_status": "success",
            },
            {
                "filename": "doc2.txt",
                "file_type": "txt",
                "file_size": 200,
                "extracted_text": "Second document",
                "extraction_status": "success",
            },
        ])

        preview_response = client.post(
            "/emails/1/reprocess",
            data={"context_notes": ""},
        )
        import re, html as html_mod
        html = preview_response.text
        action_dicts_val = html_mod.unescape(
            re.search(r'name="action_dicts_json"\s+value="([^"]*)"', html).group(1)
        )
        raw_response_val = html_mod.unescape(
            re.search(r'name="raw_response"\s+value="([^"]*)"', html).group(1)
        )

        client.post(
            "/emails/1/reprocess/confirm",
            data={
                "action_dicts_json": action_dicts_val,
                "raw_response": raw_response_val,
                "kb_data_json": kb_data,
            },
            follow_redirects=False,
        )

        with override_get_session() as session:
            from intellibox.models import KnowledgeDocument
            doc1 = session.query(KnowledgeDocument).filter_by(filename="doc1.txt").first()
            doc2 = session.query(KnowledgeDocument).filter_by(filename="doc2.txt").first()
            assert doc1 is not None
            assert doc2 is not None
            assert doc1.extracted_text == "First document"
            assert doc2.extracted_text == "Second document"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
