"""Category B: Alembic migration tests on PostgreSQL.

Verifies all 8 migrations run cleanly, downgrades work, and are idempotent.
Requires: docker compose -f docker-compose.pg-test.yml up -d
"""

import os
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, inspect, text

from tests.pg_conftest import PG_TEST_URL

pytestmark = pytest.mark.pg

# Use a separate database for migration tests to avoid conflicts
MIGRATION_DB_URL = PG_TEST_URL


def _run_alembic(*args):
    """Run alembic command with the PG test database URL."""
    env = os.environ.copy()
    env["DATABASE_URL"] = MIGRATION_DB_URL
    result = subprocess.run(
        [sys.executable, "-m", "alembic"] + list(args),
        capture_output=True,
        text=True,
        env=env,
    )
    return result


@pytest.fixture(autouse=True)
def clean_migration_state():
    """Ensure we start from a clean slate for each migration test."""
    engine = create_engine(MIGRATION_DB_URL)
    with engine.connect() as conn:
        # Drop all tables including alembic_version
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.commit()
    engine.dispose()
    yield


class TestAlembicOnPostgres:
    """All migrations run cleanly on PostgreSQL."""

    def test_upgrade_head_on_empty(self):
        """alembic upgrade head on empty PostgreSQL succeeds."""
        result = _run_alembic("upgrade", "head")
        assert result.returncode == 0, f"Upgrade failed:\n{result.stderr}"

    def test_all_tables_created(self):
        """After upgrade head, all expected tables exist."""
        _run_alembic("upgrade", "head")
        engine = create_engine(MIGRATION_DB_URL)
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        expected = {
            "emails", "actions", "assignments", "processing_log",
            "program_news_cache", "settings", "roster", "report_cache",
            "knowledge_documents", "knowledge_chunks", "alembic_version",
        }
        assert expected.issubset(tables), f"Missing: {expected - tables}"
        engine.dispose()

    def test_downgrade_to_base(self):
        """alembic downgrade base removes all application tables."""
        _run_alembic("upgrade", "head")
        result = _run_alembic("downgrade", "base")
        assert result.returncode == 0, f"Downgrade failed:\n{result.stderr}"

        engine = create_engine(MIGRATION_DB_URL)
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        app_tables = tables - {"alembic_version"}
        assert len(app_tables) == 0, f"Tables remaining: {app_tables}"
        engine.dispose()

    def test_upgrade_downgrade_upgrade_identical_schema(self):
        """Upgrade, downgrade, re-upgrade produces identical schema."""
        _run_alembic("upgrade", "head")

        engine = create_engine(MIGRATION_DB_URL)
        inspector = inspect(engine)
        schema_v1 = {t: sorted(c["name"] for c in inspector.get_columns(t))
                     for t in inspector.get_table_names() if t != "alembic_version"}
        engine.dispose()

        _run_alembic("downgrade", "base")
        _run_alembic("upgrade", "head")

        engine = create_engine(MIGRATION_DB_URL)
        inspector = inspect(engine)
        schema_v2 = {t: sorted(c["name"] for c in inspector.get_columns(t))
                     for t in inspector.get_table_names() if t != "alembic_version"}
        engine.dispose()

        assert schema_v1 == schema_v2

    def test_migration_003_inserts_default_settings(self):
        """Migration 003 inserts 4 default settings rows without datetime('now') error."""
        _run_alembic("upgrade", "head")
        engine = create_engine(MIGRATION_DB_URL)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT key FROM settings ORDER BY key"))
            keys = [row[0] for row in result]
        engine.dispose()
        assert "priority_days_threshold" in keys
        assert "priority_default" in keys
        assert "priority_high_keywords" in keys
        assert "priority_high_senders" in keys

    def test_boolean_server_defaults(self):
        """Boolean columns have correct server defaults on PostgreSQL."""
        _run_alembic("upgrade", "head")
        engine = create_engine(MIGRATION_DB_URL)
        with engine.connect() as conn:
            # Insert email without specifying 'processed' — should default to false
            conn.execute(text("""
                INSERT INTO emails (message_id, subject, from_address, to_addresses, received_date, created_at)
                VALUES ('test@bool.com', 'Test', 'a@b.com', '[]', NOW(), NOW())
            """))
            conn.commit()
            result = conn.execute(text("SELECT processed FROM emails WHERE message_id = 'test@bool.com'"))
            processed = result.scalar()
            assert processed is False

            # Insert roster member without specifying 'active' — should default to true
            conn.execute(text("""
                INSERT INTO roster (first_name, last_name, email, created_at)
                VALUES ('Test', 'User', 'test@bool.com', NOW())
            """))
            conn.commit()
            result = conn.execute(text("SELECT active FROM roster WHERE email = 'test@bool.com'"))
            active = result.scalar()
            assert active is True
        engine.dispose()

    def test_upgrade_head_idempotent(self):
        """Running upgrade head twice is a safe no-op."""
        result1 = _run_alembic("upgrade", "head")
        assert result1.returncode == 0
        result2 = _run_alembic("upgrade", "head")
        assert result2.returncode == 0
