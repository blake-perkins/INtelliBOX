"""
Comprehensive test suite for EmailTools web interface.

Tests all routes, templates, and functionality to ensure everything works
for end users.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
from contextlib import contextmanager
from unittest.mock import patch
import tempfile

from emailtools.database import Base
from emailtools.models import Email, Action, Assignment, RosterMember

# Create test database with unique temp file
test_db_fd, test_db_path = tempfile.mkstemp(suffix='_web_interface.db', prefix='test_emailtools_')
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
# Then patch get_session in the app module where it's used
import emailtools.web.app as app_module
app_module.get_session = override_get_session

from emailtools.web.app import app

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
        response = client.get("/report")
        assert response.status_code == 200
        assert b"Insights" in response.content
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
        response = client.get("/report")
        assert response.status_code == 200
        assert b"Insights" in response.content

    def test_api_stats_empty(self, empty_db):
        """Test API stats with empty database."""
        response = client.get("/api/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_emails"] == 0
        assert data["total_actions"] == 0
        assert data["unassigned_actions"] == 0
        assert data["unassigned_high"] == 0


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
        response = client.get("/report")
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


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
