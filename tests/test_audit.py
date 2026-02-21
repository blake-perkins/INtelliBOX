"""Tests for audit log feature: model, helper, endpoint integration, and audit page."""

import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta

# Ensure auth is disabled before config loads
os.environ.setdefault("AUTH_MODE", "disabled")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from intellibox.database import Base, cleanup_audit_log
from intellibox.models import Action, AuditLog, Email, RosterMember

# Create test database with unique temp file
test_db_fd, test_db_path = tempfile.mkstemp(suffix='_audit.db', prefix='test_intellibox_')
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


# Patch get_session at the database module level before importing app
import intellibox.database as database_module
import intellibox.settings_service as settings_service_module

database_module.get_session = override_get_session
settings_service_module.get_session = override_get_session

from intellibox.web.app import app  # noqa: E402

client = TestClient(app)


@pytest.fixture(scope="function")
def setup_database():
    """Create tables and populate with test data."""
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    session = TestSessionLocal()

    email = Email(
        message_id="audit-test@example.com",
        subject="Audit Test Email",
        from_address="sender@example.com",
        from_name="Sender",
        to_addresses='["team@example.com"]',
        received_date=datetime.utcnow() - timedelta(days=1),
        body_text="Test email for audit.",
        processed=True,
        processed_at=datetime.utcnow(),
    )
    session.add(email)
    session.commit()

    action = Action(
        email_id=email.id,
        title="Audit test action",
        description="Test action for audit",
        priority="high",
        category="test",
        confidence_score=0.9,
    )
    session.add(action)
    session.commit()

    roster = RosterMember(
        first_name="Alice",
        last_name="Smith",
        email="alice@example.com",
    )
    session.add(roster)
    session.commit()

    session.close()
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def empty_db():
    """Create tables with no data."""
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


class TestAuditModel:
    """Test AuditLog model directly."""

    def test_audit_log_create(self, setup_database):
        """AuditLog fields persist correctly."""
        session = TestSessionLocal()
        entry = AuditLog(
            user="testuser",
            action="create",
            resource_type="action",
            resource_id=42,
            details='{"title": "Test"}',
            ip_address="127.0.0.1",
            created_at=datetime.utcnow(),
        )
        session.add(entry)
        session.commit()

        result = session.query(AuditLog).first()
        assert result.user == "testuser"
        assert result.action == "create"
        assert result.resource_type == "action"
        assert result.resource_id == 42
        assert result.ip_address == "127.0.0.1"
        assert json.loads(result.details) == {"title": "Test"}
        session.close()

    def test_audit_log_nullable_fields(self, setup_database):
        """resource_id and details can be None."""
        session = TestSessionLocal()
        entry = AuditLog(
            user="testuser",
            action="update",
            resource_type="setting",
            created_at=datetime.utcnow(),
        )
        session.add(entry)
        session.commit()

        result = session.query(AuditLog).first()
        assert result.resource_id is None
        assert result.details is None
        session.close()


class TestAuditHelper:
    """Test log_audit helper function."""

    def test_log_audit_records_entry(self, setup_database):
        """log_audit creates a row with correct user and IP."""
        from unittest.mock import MagicMock

        from intellibox.audit import log_audit

        session = TestSessionLocal()

        mock_request = MagicMock()
        mock_request.state.user.username = "testadmin"
        mock_request.headers.get.return_value = ""
        mock_request.client.host = "10.0.0.1"

        log_audit(session, mock_request, "assign", "action", 1,
                  {"assigned_to": "alice"})
        session.commit()

        result = session.query(AuditLog).first()
        assert result.user == "testadmin"
        assert result.action == "assign"
        assert result.resource_type == "action"
        assert result.resource_id == 1
        assert result.ip_address == "10.0.0.1"
        assert json.loads(result.details) == {"assigned_to": "alice"}
        session.close()

    def test_log_audit_json_details(self, setup_database):
        """Details dict is stored as valid JSON."""
        from unittest.mock import MagicMock

        from intellibox.audit import log_audit

        session = TestSessionLocal()

        mock_request = MagicMock()
        mock_request.state.user.username = "admin"
        mock_request.headers.get.return_value = "192.168.1.1"

        log_audit(session, mock_request, "change_priority", "action", 5,
                  {"old": "low", "new": "high"})
        session.commit()

        result = session.query(AuditLog).first()
        parsed = json.loads(result.details)
        assert parsed["old"] == "low"
        assert parsed["new"] == "high"
        session.close()


class TestAuditEndpointIntegration:
    """Test that write endpoints create audit log entries."""

    def test_assign_creates_audit(self, setup_database):
        """POST /actions/{id}/assign should create an audit entry."""
        response = client.post("/actions/1/assign",
                               data={"assigned_to": "bob@example.com", "notes": ""},
                               follow_redirects=False)
        assert response.status_code == 303

        session = TestSessionLocal()
        entry = session.query(AuditLog).filter_by(action="assign").first()
        assert entry is not None
        assert entry.resource_type == "action"
        assert entry.resource_id == 1
        details = json.loads(entry.details)
        assert details["assigned_to"] == "bob@example.com"
        session.close()

    def test_change_priority_audit(self, setup_database):
        """POST /actions/{id}/priority should log old and new priority."""
        response = client.post("/actions/1/priority",
                               data={"priority": "low"},
                               follow_redirects=False)
        assert response.status_code == 303

        session = TestSessionLocal()
        entry = session.query(AuditLog).filter_by(action="change_priority").first()
        assert entry is not None
        details = json.loads(entry.details)
        assert details["old"] == "high"
        assert details["new"] == "low"
        session.close()

    def test_complete_creates_audit(self, setup_database):
        """POST /actions/{id}/complete should create an audit entry."""
        response = client.post("/actions/1/complete", follow_redirects=False)
        assert response.status_code == 303

        session = TestSessionLocal()
        entry = session.query(AuditLog).filter_by(action="complete").first()
        assert entry is not None
        assert entry.resource_id == 1
        session.close()

    def test_create_action_audit(self, setup_database):
        """POST /emails/{id}/actions/new should create an audit entry."""
        response = client.post("/emails/1/actions/new",
                               data={"title": "New task", "priority": "medium"},
                               follow_redirects=False)
        assert response.status_code == 303

        session = TestSessionLocal()
        entry = session.query(AuditLog).filter_by(action="create").first()
        assert entry is not None
        assert entry.resource_type == "action"
        details = json.loads(entry.details)
        assert details["title"] == "New task"
        session.close()

    def test_delete_action_audit(self, setup_database):
        """POST /actions/{id}/delete should create an audit entry."""
        response = client.post("/actions/1/delete", follow_redirects=False)
        assert response.status_code == 303

        session = TestSessionLocal()
        entry = session.query(AuditLog).filter_by(action="delete").first()
        assert entry is not None
        assert entry.resource_type == "action"
        assert entry.resource_id == 1
        details = json.loads(entry.details)
        assert "title" in details
        session.close()

    def test_roster_delete_audit(self, setup_database):
        """POST /roster/{id}/delete should create an audit entry."""
        response = client.post("/roster/1/delete", follow_redirects=False)
        assert response.status_code == 303

        session = TestSessionLocal()
        entry = session.query(AuditLog).filter_by(
            action="delete", resource_type="roster_member"
        ).first()
        assert entry is not None
        details = json.loads(entry.details)
        assert "name" in details
        assert "email" in details
        session.close()


class TestAuditPage:
    """Test the /audit page."""

    def test_audit_page_loads(self, setup_database):
        """GET /audit should return 200 with 'Audit Log' in content."""
        response = client.get("/audit")
        assert response.status_code == 200
        assert "Audit Log" in response.text

    def test_audit_page_empty(self, empty_db):
        """GET /audit with no data shows empty state."""
        response = client.get("/audit")
        assert response.status_code == 200
        assert "No audit entries found" in response.text

    def test_audit_page_shows_entries(self, setup_database):
        """Audit page shows entries after write operations."""
        # Create an audit entry by assigning an action
        client.post("/actions/1/assign",
                     data={"assigned_to": "test@example.com", "notes": ""},
                     follow_redirects=False)

        response = client.get("/audit")
        assert response.status_code == 200
        assert "assign" in response.text

    def test_audit_page_filters(self, setup_database):
        """Filter by action type returns correct subset."""
        # Create entries of different types
        client.post("/actions/1/assign",
                     data={"assigned_to": "test@example.com", "notes": ""},
                     follow_redirects=False)
        client.post("/actions/1/priority",
                     data={"priority": "low"},
                     follow_redirects=False)

        # Filter for assign only
        response = client.get("/audit?action=assign")
        assert response.status_code == 200
        assert "assign" in response.text


class TestAuditCleanup:
    """Test audit log cleanup."""

    def test_cleanup_audit_log(self, setup_database):
        """Old entries are deleted, recent entries are retained."""
        session = TestSessionLocal()

        # Create an old entry (400 days ago)
        old_entry = AuditLog(
            user="admin",
            action="create",
            resource_type="action",
            created_at=datetime.utcnow() - timedelta(days=400),
        )
        # Create a recent entry
        new_entry = AuditLog(
            user="admin",
            action="delete",
            resource_type="action",
            created_at=datetime.utcnow(),
        )
        session.add_all([old_entry, new_entry])
        session.commit()

        deleted = cleanup_audit_log(session, retention_days=365)
        session.commit()

        assert deleted == 1
        remaining = session.query(AuditLog).count()
        assert remaining == 1
        assert session.query(AuditLog).first().action == "delete"
        session.close()
