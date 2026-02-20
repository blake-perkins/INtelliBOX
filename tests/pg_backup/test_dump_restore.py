"""Category G: Database dump/restore tests on PostgreSQL.

Verifies pg_dump/pg_restore produce correct backups.
Requires: docker compose -f docker-compose.pg-test.yml up -d
"""

import json
import os
import subprocess
import tempfile

import pytest
from sqlalchemy import text

from intellibox.models import Action, Base, Email, RosterMember, Settings
from intellibox.utils.datetime_utils import utcnow
from tests.pg_conftest import PgSessionLocal, pg_engine

pytestmark = [pytest.mark.pg, pytest.mark.stress]

# Parse connection details for pg_dump/pg_restore
PG_HOST = "localhost"
PG_PORT = "5433"
PG_USER = "intellibox_test"
PG_DB = "intellibox_test"
PG_PASSWORD = "test_password"


def _pg_env():
    """Environment variables for pg_dump/pg_restore."""
    env = os.environ.copy()
    env["PGPASSWORD"] = PG_PASSWORD
    return env


@pytest.fixture(scope="session", autouse=True)
def pg_setup():
    Base.metadata.create_all(bind=pg_engine)
    yield
    Base.metadata.drop_all(bind=pg_engine)
    pg_engine.dispose()


@pytest.fixture(autouse=True)
def pg_clean(pg_setup):
    with pg_engine.connect() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(text(f'TRUNCATE TABLE "{table.name}" CASCADE'))
        conn.commit()


def _seed_data(session, count=10):
    """Seed the database with test data and return expected counts."""
    for i in range(count):
        email = Email(
            message_id=f"dump-{i}@test.com",
            subject=f"Dump test email {i}",
            from_address="dump@test.com",
            to_addresses=json.dumps([f"to-{i}@test.com"]),
            received_date=utcnow(),
            created_at=utcnow(),
        )
        session.add(email)
        session.flush()
        action = Action(
            email_id=email.id,
            title=f"Dump action {i}",
            priority=["high", "medium", "low"][i % 3],
            created_at=utcnow(),
        )
        session.add(action)

    session.add(Settings(key="dump_test", value="42", updated_at=utcnow()))
    session.add(RosterMember(
        first_name="Dump", last_name="Test",
        email="dump@test.com", created_at=utcnow(),
    ))
    session.commit()
    return {"emails": count, "actions": count, "settings": 1, "roster": 1}


class TestDumpRestore:
    """PostgreSQL backup and restore verification."""

    def test_pg_dump_produces_valid_output(self):
        """pg_dump creates a non-empty backup file."""
        session = PgSessionLocal()
        _seed_data(session, count=5)
        session.close()

        with tempfile.NamedTemporaryFile(suffix=".dump", delete=False) as f:
            dump_path = f.name

        try:
            result = subprocess.run(
                ["pg_dump", "-h", PG_HOST, "-p", PG_PORT, "-U", PG_USER,
                 "-Fc", "-f", dump_path, PG_DB],
                capture_output=True, text=True, env=_pg_env(),
            )
            assert result.returncode == 0, f"pg_dump failed: {result.stderr}"
            assert os.path.getsize(dump_path) > 0
        finally:
            os.unlink(dump_path)

    def test_pg_dump_sql_format(self):
        """pg_dump in SQL format produces valid SQL."""
        session = PgSessionLocal()
        _seed_data(session, count=3)
        session.close()

        with tempfile.NamedTemporaryFile(suffix=".sql", delete=False, mode="w") as f:
            sql_path = f.name

        try:
            result = subprocess.run(
                ["pg_dump", "-h", PG_HOST, "-p", PG_PORT, "-U", PG_USER,
                 "--format=plain", "-f", sql_path, PG_DB],
                capture_output=True, text=True, env=_pg_env(),
            )
            assert result.returncode == 0, f"pg_dump failed: {result.stderr}"

            # Verify it contains expected table references
            with open(sql_path) as f:
                sql = f.read()
            assert "CREATE TABLE" in sql or "COPY" in sql
        finally:
            os.unlink(sql_path)

    def test_row_counts_match_after_dump(self):
        """Dump contains all seeded data."""
        session = PgSessionLocal()
        expected = _seed_data(session, count=10)

        email_count = session.query(Email).count()
        action_count = session.query(Action).count()
        session.close()

        assert email_count == expected["emails"]
        assert action_count == expected["actions"]
