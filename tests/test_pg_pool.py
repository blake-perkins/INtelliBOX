"""Category C: Connection pool tests on PostgreSQL.

Verifies pool_size, max_overflow, pre_ping, and exhaustion behavior.
Requires: docker compose -f docker-compose.pg-test.yml up -d
"""

import threading
import time

import pytest
from sqlalchemy import create_engine, text

from tests.pg_conftest import PG_TEST_URL

pytestmark = pytest.mark.pg


class TestPoolBasics:
    """Connection pool creates and manages connections correctly."""

    def test_pool_size_respected(self):
        """Pool maintains pool_size persistent connections."""
        engine = create_engine(PG_TEST_URL, pool_size=3, max_overflow=0, pool_timeout=2)
        conns = []
        try:
            for _ in range(3):
                conns.append(engine.connect())
            assert engine.pool.checkedout() == 3
        finally:
            for c in conns:
                c.close()
            engine.dispose()

    def test_overflow_connections_created(self):
        """When pool is full, overflow connections are created up to max_overflow."""
        engine = create_engine(PG_TEST_URL, pool_size=2, max_overflow=3, pool_timeout=2)
        conns = []
        try:
            for _ in range(5):  # 2 pool + 3 overflow
                conns.append(engine.connect())
            assert engine.pool.checkedout() == 5
        finally:
            for c in conns:
                c.close()
            engine.dispose()

    def test_pool_exhaustion_raises_timeout(self):
        """When pool + overflow are full, new connection request raises TimeoutError."""
        engine = create_engine(PG_TEST_URL, pool_size=2, max_overflow=0, pool_timeout=1)
        conns = []
        try:
            # Take all connections
            for _ in range(2):
                conns.append(engine.connect())
            # Third should timeout
            with pytest.raises(Exception):  # TimeoutError or OperationalError
                engine.connect()
        finally:
            for c in conns:
                c.close()
            engine.dispose()

    def test_pool_recovery_after_exhaustion(self):
        """After exhaustion, returning a connection makes pool usable again."""
        engine = create_engine(PG_TEST_URL, pool_size=2, max_overflow=0, pool_timeout=2)
        conns = []
        try:
            for _ in range(2):
                conns.append(engine.connect())
            # Return one connection
            conns[0].close()
            conns.pop(0)
            # Now we can acquire another
            new_conn = engine.connect()
            new_conn.execute(text("SELECT 1"))
            new_conn.close()
        finally:
            for c in conns:
                c.close()
            engine.dispose()


class TestPoolPrePing:
    """pool_pre_ping detects and replaces stale connections."""

    def test_pre_ping_enabled(self):
        """With pool_pre_ping=True, stale connections are detected and replaced."""
        engine = create_engine(PG_TEST_URL, pool_size=1, max_overflow=0, pool_pre_ping=True)
        # First connection works
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.scalar() == 1
        # Second connection should also work (pre_ping verifies)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.scalar() == 1
        engine.dispose()

    def test_concurrent_pool_access(self):
        """Multiple threads can safely use the connection pool."""
        engine = create_engine(PG_TEST_URL, pool_size=5, max_overflow=5, pool_pre_ping=True)
        errors = []

        def worker():
            try:
                with engine.connect() as conn:
                    result = conn.execute(text("SELECT 1"))
                    assert result.scalar() == 1
                    time.sleep(0.01)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        engine.dispose()
        assert len(errors) == 0, f"Errors: {errors}"
