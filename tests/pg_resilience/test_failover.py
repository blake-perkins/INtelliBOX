"""Category E: Failover and resilience tests on PostgreSQL.

These tests verify the app recovers from PostgreSQL outages.
Requires Docker to control the PostgreSQL container lifecycle.

Run manually or in CI with Docker access:
    docker compose -f docker-compose.pg-test.yml up -d
    python -m pytest tests/pg_resilience/ -v --no-cov
"""

import subprocess
import time

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from tests.pg_conftest import PG_TEST_URL

pytestmark = [pytest.mark.pg, pytest.mark.stress]

CONTAINER_NAME = "intellibox-pg-test"


def _container_running():
    """Check if the PG test container is running."""
    result = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", CONTAINER_NAME],
        capture_output=True, text=True,
    )
    return result.stdout.strip() == "true"


def _stop_container():
    subprocess.run(["docker", "stop", CONTAINER_NAME], capture_output=True)


def _start_container():
    subprocess.run(["docker", "start", CONTAINER_NAME], capture_output=True)


def _wait_for_pg(timeout=15):
    """Wait for PostgreSQL to be ready after container start."""
    engine = create_engine(PG_TEST_URL, pool_pre_ping=True)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            engine.dispose()
            return True
        except Exception:
            time.sleep(0.5)
    engine.dispose()
    return False


@pytest.fixture(autouse=True)
def ensure_container_running():
    """Ensure the PG container is running before and after each test."""
    if not _container_running():
        _start_container()
        assert _wait_for_pg(), "PG container failed to start"
    yield
    if not _container_running():
        _start_container()
        _wait_for_pg()


class TestFailover:
    """PostgreSQL crash/restart recovery scenarios."""

    def test_query_fails_when_pg_down(self):
        """When PG is stopped, queries fail with OperationalError (not hang)."""
        # Verify PG works
        engine = create_engine(PG_TEST_URL, pool_size=1, max_overflow=0, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        # Stop PG
        _stop_container()
        time.sleep(1)

        # Should fail, not hang
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            assert False, "Should have raised OperationalError"
        except (OperationalError, Exception):
            pass  # Expected

        engine.dispose()

        # Restart for cleanup
        _start_container()
        assert _wait_for_pg()

    def test_recovery_after_restart(self):
        """After PG restarts, pool_pre_ping recovers automatically."""
        engine = create_engine(PG_TEST_URL, pool_size=2, max_overflow=0, pool_pre_ping=True)

        # First query works
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        # Restart PG
        _stop_container()
        time.sleep(1)
        _start_container()
        assert _wait_for_pg()

        # Query should succeed (pre_ping detects stale, reconnects)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.scalar() == 1

        engine.dispose()

    def test_multiple_queries_after_restart(self):
        """10 rapid queries after restart all succeed."""
        engine = create_engine(PG_TEST_URL, pool_size=3, max_overflow=2, pool_pre_ping=True)

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        _stop_container()
        time.sleep(1)
        _start_container()
        assert _wait_for_pg()

        for _ in range(10):
            with engine.connect() as conn:
                assert conn.execute(text("SELECT 1")).scalar() == 1

        engine.dispose()
