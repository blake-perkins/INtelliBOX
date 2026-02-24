"""Tests for the API Usage telemetry dashboard and logging."""

import os
import tempfile
from contextlib import contextmanager
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from intellibox.ai.types import APIResponse
from intellibox.models import APIUsageLog, Base
from intellibox.utils.datetime_utils import utcnow

# --- Test database setup ---
os.environ.setdefault("AUTH_MODE", "disabled")

test_db_fd, test_db_path = tempfile.mkstemp(suffix="_api_usage.db", prefix="test_intellibox_")
TEST_DATABASE_URL = f"sqlite:///{test_db_path}"
test_engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@contextmanager
def override_get_session():
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


# Patch before importing the app
import intellibox.database as database_module  # noqa: E402
import intellibox.settings_service as settings_service_module  # noqa: E402

database_module.get_session = override_get_session
settings_service_module.get_session = override_get_session

from intellibox.web.app import app  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def setup_database():
    """Create tables fresh for each test."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


def _seed_usage_data():
    """Insert sample APIUsageLog rows."""
    now = utcnow()
    with override_get_session() as session:
        rows = [
            APIUsageLog(
                call_type="extract_actions",
                model="gpt-4o-mini",
                prompt_tokens=500,
                completion_tokens=200,
                total_tokens=700,
                latency_ms=1200,
                retry_count=0,
                status="success",
                created_at=now - timedelta(hours=1),
            ),
            APIUsageLog(
                call_type="extract_actions",
                model="gpt-4o-mini",
                prompt_tokens=450,
                completion_tokens=180,
                total_tokens=630,
                latency_ms=1100,
                retry_count=0,
                status="success",
                created_at=now - timedelta(hours=2),
            ),
            APIUsageLog(
                call_type="generate_program_news",
                model="gpt-4o-mini",
                prompt_tokens=800,
                completion_tokens=300,
                total_tokens=1100,
                latency_ms=2500,
                retry_count=1,
                status="success",
                created_at=now - timedelta(days=1),
            ),
            APIUsageLog(
                call_type="generate_report_insights",
                model="gpt-4o-mini",
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                latency_ms=0,
                retry_count=0,
                status="error",
                error_message="Rate limit exceeded",
                created_at=now - timedelta(days=2),
            ),
        ]
        for row in rows:
            session.add(row)
        session.commit()


# --- Dashboard Route Tests ---


class TestAPIUsageDashboard:

    def test_dashboard_loads_empty(self):
        """Dashboard loads with no data."""
        r = client.get("/api-usage")
        assert r.status_code == 200
        assert "API Usage" in r.text
        assert "No API calls recorded" in r.text

    def test_dashboard_loads_with_data(self):
        """Dashboard loads and shows summary data."""
        _seed_usage_data()
        r = client.get("/api-usage")
        assert r.status_code == 200
        assert "API Usage" in r.text
        assert "API Calls" in r.text
        assert "Total Tokens" in r.text
        assert "Est. Cost" in r.text

    def test_dashboard_shows_call_types(self):
        """Dashboard shows breakdown by call type."""
        _seed_usage_data()
        r = client.get("/api-usage")
        assert r.status_code == 200
        assert "Extract Actions" in r.text
        assert "Generate Program News" in r.text

    def test_dashboard_shows_recent_calls(self):
        """Dashboard shows the recent calls table."""
        _seed_usage_data()
        r = client.get("/api-usage")
        assert r.status_code == 200
        assert "gpt-4o-mini" in r.text
        assert "OK" in r.text
        assert "ERR" in r.text

    def test_dashboard_days_filter(self):
        """Dashboard respects the days filter parameter."""
        _seed_usage_data()
        r = client.get("/api-usage?days=7")
        assert r.status_code == 200
        assert 'value="7" selected' in r.text

    def test_dashboard_invalid_days_defaults(self):
        """Invalid days parameter falls back to 30."""
        r = client.get("/api-usage?days=abc")
        assert r.status_code == 200

    def test_dashboard_shows_error_count(self):
        """Error count is displayed when errors exist."""
        _seed_usage_data()
        r = client.get("/api-usage")
        assert r.status_code == 200
        assert "error" in r.text.lower()

    def test_dashboard_shows_token_distribution(self):
        """Token distribution section shows input/output split."""
        _seed_usage_data()
        r = client.get("/api-usage")
        assert r.status_code == 200
        assert "Input:" in r.text
        assert "Output:" in r.text


# --- Usage Logger Tests ---


class TestUsageLogger:

    def test_log_api_usage_creates_row(self):
        """log_api_usage persists an APIUsageLog row."""
        from intellibox.ai.usage_logger import log_api_usage

        api_response = APIResponse(
            content="test content",
            model="gpt-4o-mini",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            latency_ms=800,
            retry_count=0,
        )

        log_api_usage("extract_actions", api_response, email_id=None)

        with override_get_session() as session:
            rows = session.query(APIUsageLog).all()
            assert len(rows) == 1
            assert rows[0].call_type == "extract_actions"
            assert rows[0].model == "gpt-4o-mini"
            assert rows[0].prompt_tokens == 100
            assert rows[0].completion_tokens == 50
            assert rows[0].total_tokens == 150
            assert rows[0].latency_ms == 800
            assert rows[0].status == "success"

    def test_log_api_error_creates_error_row(self):
        """log_api_error persists an error row."""
        from intellibox.ai.usage_logger import log_api_error

        log_api_error(
            "generate_program_news",
            Exception("Connection timeout"),
            model="gpt-4o-mini",
        )

        with override_get_session() as session:
            rows = session.query(APIUsageLog).all()
            assert len(rows) == 1
            assert rows[0].call_type == "generate_program_news"
            assert rows[0].status == "error"
            assert "Connection timeout" in rows[0].error_message
            assert rows[0].total_tokens == 0

    def test_log_api_usage_best_effort(self):
        """log_api_usage doesn't raise on failure (best-effort)."""
        from intellibox.ai.usage_logger import log_api_usage

        api_response = APIResponse(content="test")
        # This should not raise even though email_id references a non-existent email
        # (FK constraint won't fire because we use SET NULL and the value is just an int)
        log_api_usage("extract_actions", api_response, email_id=99999)


# --- Maintenance Tests ---


class TestAPIUsageCleanup:

    def test_cleanup_deletes_old_rows(self):
        """cleanup_api_usage_log removes rows older than retention period."""
        from intellibox.database import cleanup_api_usage_log

        now = utcnow()
        with override_get_session() as session:
            # Old row (200 days ago)
            session.add(APIUsageLog(
                call_type="extract_actions",
                model="gpt-4o-mini",
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
                latency_ms=500,
                status="success",
                created_at=now - timedelta(days=200),
            ))
            # Recent row (1 day ago)
            session.add(APIUsageLog(
                call_type="extract_actions",
                model="gpt-4o-mini",
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
                latency_ms=500,
                status="success",
                created_at=now - timedelta(days=1),
            ))
            session.commit()

            deleted = cleanup_api_usage_log(session, retention_days=180)
            session.commit()

            assert deleted == 1
            remaining = session.query(APIUsageLog).count()
            assert remaining == 1
