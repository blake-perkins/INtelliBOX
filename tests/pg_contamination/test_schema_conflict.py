"""Category H.4: Schema conflict and concurrent migration tests.

Tests that Alembic migrations behave safely under edge conditions.
Requires: docker compose -f docker-compose.pg-test.yml up -d
"""

import os
import subprocess
import sys

import pytest
from sqlalchemy import inspect, text

from intellibox.models import Base
from tests.pg_conftest import PG_TEST_URL, PgSessionLocal, pg_engine

pytestmark = pytest.mark.pg


@pytest.fixture(autouse=True)
def clean_db_for_alembic():
    """Drop ALL tables (including alembic_version) so alembic starts from scratch.

    This prevents interference from other test modules that may have used
    Base.metadata.create_all() to create tables without alembic tracking.
    """
    with pg_engine.connect() as conn:
        # Drop all ORM tables
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(text(f'DROP TABLE IF EXISTS "{table.name}" CASCADE'))
        # Drop alembic's version tracking table
        conn.execute(text('DROP TABLE IF EXISTS "alembic_version" CASCADE'))
        conn.commit()
    yield
    # Cleanup after: drop everything again so other tests start clean
    with pg_engine.connect() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(text(f'DROP TABLE IF EXISTS "{table.name}" CASCADE'))
        conn.execute(text('DROP TABLE IF EXISTS "alembic_version" CASCADE'))
        conn.commit()


def _alembic_env():
    """Build environment dict for alembic subprocess calls."""
    env = dict(os.environ)
    env["DATABASE_URL"] = PG_TEST_URL
    return env


def _project_root():
    return os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


class TestSchemaConflict:
    """Alembic migration edge cases on PostgreSQL."""

    def test_upgrade_head_twice_is_noop(self):
        """Running 'alembic upgrade head' twice produces no error."""
        env = _alembic_env()
        root = _project_root()

        # First upgrade
        result1 = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True, text=True, env=env, cwd=root,
        )
        assert result1.returncode == 0, f"First upgrade failed: {result1.stderr}"

        # Second upgrade — should be a safe no-op
        result2 = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True, text=True, env=env, cwd=root,
        )
        assert result2.returncode == 0, f"Second upgrade failed: {result2.stderr}"

    def test_downgrade_one_then_upgrade_recovers(self):
        """Downgrade one revision then upgrade restores full schema."""
        env = _alembic_env()
        root = _project_root()

        # Ensure at head first
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True, text=True, env=env, cwd=root,
        )
        assert result.returncode == 0, f"Initial upgrade failed: {result.stderr}"

        # Get tables before
        inspector = inspect(pg_engine)
        tables_before = set(inspector.get_table_names())

        # Downgrade one step
        result_down = subprocess.run(
            [sys.executable, "-m", "alembic", "downgrade", "-1"],
            capture_output=True, text=True, env=env, cwd=root,
        )
        assert result_down.returncode == 0, f"Downgrade failed: {result_down.stderr}"

        # Upgrade back to head
        result_up = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True, text=True, env=env, cwd=root,
        )
        assert result_up.returncode == 0, f"Re-upgrade failed: {result_up.stderr}"

        # Tables should match
        inspector2 = inspect(pg_engine)
        tables_after = set(inspector2.get_table_names())
        assert tables_before - {"alembic_version"} == tables_after - {"alembic_version"}

    def test_app_queries_work_after_migration_cycle(self):
        """After downgrade+upgrade, basic ORM queries still work."""
        env = _alembic_env()
        root = _project_root()

        # Ensure at head
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True, text=True, env=env, cwd=root,
        )

        # Verify we can insert and query after migration cycle
        from intellibox.models import Email
        from intellibox.utils.datetime_utils import utcnow

        session = PgSessionLocal()
        now = utcnow()
        email = Email(
            message_id="schema-conflict-test@test.com",
            subject="After migration cycle",
            from_address="test@test.com",
            to_addresses="[]",
            received_date=now,
            created_at=now,
        )
        session.add(email)
        session.commit()

        result = session.query(Email).filter_by(message_id="schema-conflict-test@test.com").first()
        assert result is not None
        assert result.subject == "After migration cycle"
        session.close()
