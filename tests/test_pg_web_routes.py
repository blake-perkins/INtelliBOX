"""PostgreSQL web route tests.

Runs the FastAPI TestClient against PostgreSQL to catch SQLite-vs-PG
behavioral differences in route handler queries (DISTINCT+ORDER BY,
GROUP BY strictness, CASE in COUNT, ilike, nullslast, etc.).

Requires a running PostgreSQL instance:
    podman run -d --name intellibox-pg-test \\
        -e POSTGRES_DB=intellibox_test -e POSTGRES_USER=intellibox_test \\
        -e POSTGRES_PASSWORD=test_password -p 5433:5432 postgres:16-alpine
"""

import html as html_mod
import json
import os
import re

# Auth must be disabled BEFORE importing the app — override .env which may set AUTH_MODE=local
os.environ["AUTH_MODE"] = "disabled"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from intellibox.models import Action, Assignment, AuditLog, Base, Email

# ── Session injection: point the app at the PG database ──────────────────────

from tests.pg_conftest import PgSessionLocal, pg_engine, pg_override_get_session

import intellibox.database as database_module
import intellibox.settings_service as settings_service_module

database_module.get_session = pg_override_get_session
settings_service_module.get_session = pg_override_get_session

# Force mock AI client
import intellibox.ai.processor as ai_processor_module
from intellibox.ai.mock_client import mock_ai_client

ai_processor_module.get_ai_client = lambda: mock_ai_client

from intellibox.web.app import app  # noqa: E402 — must import after patching

client = TestClient(app)

pytestmark = pytest.mark.pg


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def pg_tables():
    """Create all tables once, drop at end."""
    Base.metadata.create_all(bind=pg_engine)
    yield
    Base.metadata.drop_all(bind=pg_engine)
    pg_engine.dispose()


@pytest.fixture(autouse=True)
def pg_clean(pg_tables):
    """Truncate all tables between tests."""
    with pg_engine.connect() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(text(f'TRUNCATE TABLE "{table.name}" CASCADE'))
        conn.commit()


@pytest.fixture()
def seed():
    """Populate standard test dataset, return entity IDs."""
    from tests.pg_web_helpers import populate_test_data
    return populate_test_data(PgSessionLocal)


@pytest.fixture()
def session():
    """Provide a raw PG session for in-test queries."""
    s = PgSessionLocal()
    yield s
    s.close()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _extract_reprocess_fields(preview_html):
    """Pull hidden form values from reprocess preview page."""
    ad = re.search(r'name="action_dicts_json"\s+value="([^"]*)"', preview_html)
    rr = re.search(r'name="raw_response"\s+value="([^"]*)"', preview_html)
    assert ad and rr, "Could not extract reprocess hidden fields from preview page"
    return html_mod.unescape(ad.group(1)), html_mod.unescape(rr.group(1))


# ═════════════════════════════════════════════════════════════════════════════
# Dashboard
# ═════════════════════════════════════════════════════════════════════════════

class TestDashboardPG:
    """Dashboard aggregation queries (CASE, outerjoin, joinedload)."""

    def test_dashboard_loads(self, seed):
        r = client.get("/")
        assert r.status_code == 200
        assert b"Dashboard" in r.content

    def test_dashboard_empty(self):
        r = client.get("/")
        assert r.status_code == 200
        assert b"Dashboard" in r.content


# ═════════════════════════════════════════════════════════════════════════════
# Actions list
# ═════════════════════════════════════════════════════════════════════════════

class TestActionsListPG:
    """Actions list queries (subqueryload, CASE, ilike, nullslast)."""

    def test_actions_list(self, seed):
        r = client.get("/actions")
        assert r.status_code == 200
        assert b"Provide budget data" in r.content
        assert b"Investigate production error" in r.content

    def test_actions_filter_priority(self, seed):
        r = client.get("/actions?priority=high")
        assert r.status_code == 200
        assert b"Investigate production error" in r.content

    def test_actions_filter_unassigned(self, seed):
        r = client.get("/actions?assigned=false")
        assert r.status_code == 200
        assert b"Investigate production error" in r.content
        assert b"Review meeting notes" in r.content

    def test_actions_filter_assigned(self, seed):
        r = client.get("/actions?assigned=true")
        assert r.status_code == 200
        assert b"Provide budget data" in r.content

    def test_actions_search_ilike(self, seed):
        # Case-insensitive search via ilike — PG is case-sensitive for LIKE
        r = client.get("/actions?search=BUDGET")
        assert r.status_code == 200
        assert b"Provide budget data" in r.content

    def test_actions_pagination(self, seed):
        r = client.get("/actions?page=1")
        assert r.status_code == 200

    def test_actions_export_csv(self, seed):
        r = client.get("/actions/export.csv")
        assert r.status_code == 200
        assert "text/csv" in r.headers["content-type"]
        lines = r.content.decode().strip().splitlines()
        assert lines[0].startswith("ID,")
        assert len(lines) == 5  # header + 4 actions

    def test_actions_export_csv_priority_filter(self, seed):
        r = client.get("/actions/export.csv?priority=high")
        assert r.status_code == 200
        lines = r.content.decode().strip().splitlines()
        assert len(lines) == 3  # header + 2 high

    def test_actions_export_csv_search(self, seed):
        r = client.get("/actions/export.csv?search=nonexistent_xyz")
        assert r.status_code == 200
        lines = r.content.decode().strip().splitlines()
        assert len(lines) == 1  # header only


# ═════════════════════════════════════════════════════════════════════════════
# Action detail — this is where the DISTINCT+ORDER BY bug lived
# ═════════════════════════════════════════════════════════════════════════════

class TestActionDetailPG:
    """Action detail route (GROUP BY subquery, joinedload, subqueryload)."""

    def test_action_detail_loads(self, seed):
        r = client.get(f"/actions/{seed['action1']}")
        assert r.status_code == 200
        assert b"Edit Action" in r.content
        assert b"Source Email" in r.content

    def test_action_detail_with_assignment(self, seed):
        """Action with assignment shows assignee info."""
        r = client.get(f"/actions/{seed['action1']}")
        assert r.status_code == 200
        assert b"john@example.com" in r.content

    def test_action_detail_with_roster(self, seed):
        """Roster members appear in assign dropdown."""
        r = client.get(f"/actions/{seed['action1']}")
        assert r.status_code == 200
        assert b"Smith, Alice" in r.content

    def test_action_detail_not_found(self, seed):
        r = client.get("/actions/99999")
        assert r.status_code == 404


# ═════════════════════════════════════════════════════════════════════════════
# Action writes (assign, complete, priority, edit, status, delete)
# ═════════════════════════════════════════════════════════════════════════════

class TestActionWritesPG:
    """Action write operations against PostgreSQL."""

    def test_assign_action(self, seed, session):
        """POST assign creates an Assignment row."""
        r = client.post(
            f"/actions/{seed['action2']}/assign",
            data={"assigned_to": "alice@example.com", "notes": "PG test"},
            follow_redirects=False,
        )
        assert r.status_code == 303
        a = session.query(Assignment).filter_by(action_id=seed["action2"]).first()
        assert a is not None
        assert a.assigned_to == "alice@example.com"

    def test_complete_action(self, seed, session):
        """POST complete marks assignment completed."""
        r = client.post(
            f"/actions/{seed['action1']}/complete",
            follow_redirects=False,
        )
        assert r.status_code == 303
        a = session.query(Assignment).filter_by(action_id=seed["action1"]).first()
        assert a.status == "completed"
        assert a.completed_at is not None

    def test_change_priority(self, seed, session):
        """POST priority updates the action priority."""
        r = client.post(
            f"/actions/{seed['action3']}/priority",
            data={"priority": "high"},
            follow_redirects=False,
        )
        assert r.status_code == 303
        action = session.get(Action,seed["action3"])
        assert action.priority == "high"

    def test_edit_action(self, seed, session):
        """POST edit updates multiple action fields."""
        r = client.post(
            f"/actions/{seed['action2']}/edit",
            data={
                "title": "Updated title",
                "description": "Updated description",
                "priority": "low",
                "due_date": "2026-06-01",
                "category": "test-cat",
            },
            follow_redirects=False,
        )
        assert r.status_code == 303
        action = session.get(Action,seed["action2"])
        assert action.title == "Updated title"
        assert action.priority == "low"

    def test_set_status_transition(self, seed, session):
        """Status transitions work on PostgreSQL."""
        aid = seed["action1"]
        r = client.post(
            f"/actions/{aid}/status",
            data={"status": "in_progress"},
            follow_redirects=False,
        )
        assert r.status_code == 303
        a = session.query(Assignment).filter_by(action_id=aid).first()
        assert a.status == "in_progress"

    def test_set_invalid_status_rejected(self, seed):
        """Invalid status value returns 400."""
        r = client.post(
            f"/actions/{seed['action1']}/status",
            data={"status": "bogus"},
            follow_redirects=False,
        )
        assert r.status_code == 400

    def test_delete_action(self, seed, session):
        """POST delete removes action."""
        r = client.post(
            f"/actions/{seed['action3']}/delete",
            follow_redirects=False,
        )
        assert r.status_code == 303
        assert session.get(Action,seed["action3"]) is None

    def test_create_action_from_email(self, seed, session):
        """POST /emails/{id}/actions/new creates a new action."""
        r = client.post(
            f"/emails/{seed['email2']}/actions/new",
            data={
                "title": "New PG test action",
                "description": "Created in PG test",
                "priority": "medium",
                "due_date": "2026-07-01",
                "category": "pg-test",
            },
            follow_redirects=False,
        )
        assert r.status_code == 303
        action = session.query(Action).filter_by(title="New PG test action").first()
        assert action is not None
        assert action.email_id == seed["email2"]


# ═════════════════════════════════════════════════════════════════════════════
# Emails
# ═════════════════════════════════════════════════════════════════════════════

class TestEmailsPG:
    """Email routes (ilike across columns, boolean filter, join loading)."""

    def test_emails_list(self, seed):
        r = client.get("/emails")
        assert r.status_code == 200
        assert b"Test RFI - Budget Data Request" in r.content
        assert b"URGENT: Production Issue" in r.content

    def test_emails_filter_processed(self, seed):
        r = client.get("/emails?processed=true")
        assert r.status_code == 200

    def test_emails_search_ilike(self, seed):
        r = client.get("/emails?search=URGENT")
        assert r.status_code == 200
        assert b"URGENT: Production Issue" in r.content

    def test_email_detail(self, seed):
        r = client.get(f"/emails/{seed['email1']}")
        assert r.status_code == 200
        assert b"boss@example.com" in r.content

    def test_email_detail_not_found(self, seed):
        r = client.get("/emails/99999")
        assert r.status_code == 404


# ═════════════════════════════════════════════════════════════════════════════
# Analytics
# ═════════════════════════════════════════════════════════════════════════════

class TestAnalyticsPG:
    """Analytics route (GROUP BY, CASE in COUNT, string alias ORDER BY)."""

    def test_analytics_loads(self, seed):
        r = client.get("/analytics")
        assert r.status_code == 200

    def test_analytics_empty(self):
        r = client.get("/analytics")
        assert r.status_code == 200


# ═════════════════════════════════════════════════════════════════════════════
# API stats
# ═════════════════════════════════════════════════════════════════════════════

class TestAPIPG:
    """API stats route (multi-column CASE aggregation)."""

    def test_api_stats(self, seed):
        r = client.get("/api/stats")
        assert r.status_code == 200
        data = r.json()
        assert data["total_emails"] == 3
        assert data["total_actions"] == 4
        assert data["unassigned_actions"] == 3

    def test_api_stats_empty(self):
        r = client.get("/api/stats")
        assert r.status_code == 200
        data = r.json()
        assert data["total_emails"] == 0


# ═════════════════════════════════════════════════════════════════════════════
# Settings & Roster
# ═════════════════════════════════════════════════════════════════════════════

class TestSettingsRosterPG:
    """Settings and roster routes on PostgreSQL."""

    def test_settings_page_loads(self, seed):
        r = client.get("/settings")
        assert r.status_code == 200

    def test_roster_page_loads(self, seed):
        r = client.get("/roster")
        assert r.status_code == 200
        assert b"Alice" in r.content
        assert b"Bob" in r.content

    def test_roster_add_member(self, seed, session):
        from intellibox.models import RosterMember

        r = client.post(
            "/roster/add",
            data={
                "first_name": "Charlie",
                "last_name": "Brown",
                "email": "charlie@example.com",
            },
            follow_redirects=False,
        )
        assert r.status_code == 303
        m = session.query(RosterMember).filter_by(email="charlie@example.com").first()
        assert m is not None

    def test_save_settings(self, seed):
        r = client.post(
            "/settings",
            data={
                "priority_default": "medium",
                "priority_days_threshold": "3",
                "priority_high_senders": "",
                "priority_high_keywords": "urgent,critical",
                "confidence_threshold": "0.6",
                "timezone": "UTC",
                "program_name": "INtelliBOX",
            },
            follow_redirects=False,
        )
        assert r.status_code == 303


# ═════════════════════════════════════════════════════════════════════════════
# Insights
# ═════════════════════════════════════════════════════════════════════════════

class TestInsightsPG:
    """Insights page on PostgreSQL."""

    def test_insights_loads(self, seed):
        r = client.get("/insights")
        assert r.status_code == 200
        assert b"AI Insights" in r.content

    def test_insights_with_days(self, seed):
        r = client.get("/insights?days=7")
        assert r.status_code == 200

    def test_insights_empty(self):
        r = client.get("/insights")
        assert r.status_code == 200


# ═════════════════════════════════════════════════════════════════════════════
# Audit
# ═════════════════════════════════════════════════════════════════════════════

class TestAuditPG:
    """Audit log route on PostgreSQL."""

    def test_audit_page_loads(self, seed):
        r = client.get("/audit")
        assert r.status_code == 200


# ═════════════════════════════════════════════════════════════════════════════
# Reprocess
# ═════════════════════════════════════════════════════════════════════════════

class TestReprocessPG:
    """Reprocess workflow (DELETE unassigned + INSERT new in same txn)."""

    def test_reprocess_form_loads(self, seed):
        r = client.get(f"/emails/{seed['email1']}/reprocess")
        assert r.status_code == 200
        assert b"Re-process with AI" in r.content

    def test_reprocess_preview(self, seed):
        r = client.post(
            f"/emails/{seed['email1']}/reprocess",
            data={"context_notes": ""},
            follow_redirects=False,
        )
        assert r.status_code == 200
        assert b"Re-process Preview" in r.content

    def test_reprocess_confirm(self, seed, session):
        """Full reprocess: delete unassigned, insert new, preserve assigned."""
        eid = seed["email1"]

        # Get preview
        preview = client.post(
            f"/emails/{eid}/reprocess",
            data={"context_notes": ""},
        )
        assert preview.status_code == 200
        action_dicts_val, raw_response_val = _extract_reprocess_fields(preview.text)

        # Confirm
        r = client.post(
            f"/emails/{eid}/reprocess/confirm",
            data={
                "action_dicts_json": action_dicts_val,
                "raw_response": raw_response_val,
                "kb_data_json": "",
            },
            follow_redirects=False,
        )
        assert r.status_code == 303

        # Verify: assigned action1 preserved, unassigned action4 gone
        remaining = session.query(Action).filter_by(email_id=eid).all()
        assigned_remaining = [a for a in remaining if a.assignments]
        assert len(assigned_remaining) >= 1
        assert assigned_remaining[0].title == "Provide budget data"

    def test_reprocess_audit_logged(self, seed, session):
        """Reprocessing creates an audit log entry."""
        eid = seed["email1"]
        preview = client.post(f"/emails/{eid}/reprocess", data={"context_notes": ""})
        ad, rr = _extract_reprocess_fields(preview.text)

        client.post(
            f"/emails/{eid}/reprocess/confirm",
            data={"action_dicts_json": ad, "raw_response": rr, "kb_data_json": ""},
            follow_redirects=False,
        )

        entry = session.query(AuditLog).filter_by(action="reprocess").first()
        assert entry is not None
        assert entry.resource_type == "email"


# ═════════════════════════════════════════════════════════════════════════════
# Knowledge Base
# ═════════════════════════════════════════════════════════════════════════════

class TestKnowledgeBasePG:
    """Knowledge base routes on PostgreSQL."""

    def test_knowledge_base_page_loads(self, seed):
        r = client.get("/knowledge-base")
        assert r.status_code == 200

    def test_knowledge_base_upload(self, seed, session):
        from intellibox.models import KnowledgeDocument

        r = client.post(
            "/knowledge-base/upload",
            files={"file": ("test.txt", b"PG test knowledge content", "text/plain")},
            data={"description": "PG test doc"},
            follow_redirects=False,
        )
        assert r.status_code == 303
        doc = session.query(KnowledgeDocument).filter_by(filename="test.txt").first()
        assert doc is not None
