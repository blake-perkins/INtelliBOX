"""Category D.2: Connection pool stress tests.

Tests pool exhaustion, recovery, and concurrent access patterns.
Requires: docker compose -f docker-compose.pg-test.yml --profile stress up -d
"""

import os
import threading
import time

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

pytestmark = [pytest.mark.pg, pytest.mark.stress]

STRESS_URL = os.environ.get(
    "PG_STRESS_DATABASE_URL",
    "postgresql+psycopg://intellibox_stress:stress_password@localhost:5434/intellibox_stress",
)


@pytest.fixture(scope="module")
def tight_pool_engine():
    """Engine with deliberately small pool for exhaustion testing."""
    engine = create_engine(
        STRESS_URL,
        poolclass=QueuePool,
        pool_size=3,
        max_overflow=0,
        pool_timeout=2,  # 2 second timeout
        pool_pre_ping=True,
    )
    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def medium_pool_engine():
    """Engine with moderate pool for concurrent access testing."""
    engine = create_engine(
        STRESS_URL,
        poolclass=QueuePool,
        pool_size=10,
        max_overflow=10,
        pool_timeout=10,
        pool_pre_ping=True,
    )
    yield engine
    engine.dispose()


class TestPoolExhaustion:
    """Pool exhaustion behavior under load."""

    def test_exhaust_pool_raises_timeout(self, tight_pool_engine):
        """When pool is fully exhausted, next acquire raises TimeoutError (not hang)."""
        engine = tight_pool_engine
        held_connections = []

        try:
            # Hold all 3 connections from the pool
            for _ in range(3):
                conn = engine.connect()
                held_connections.append(conn)

            # Next connection should timeout, not hang forever
            start = time.perf_counter()
            with pytest.raises(Exception) as exc_info:
                engine.connect()
            elapsed = time.perf_counter() - start

            # Should timeout around 2s (pool_timeout), not hang
            assert elapsed < 5, f"Took {elapsed:.1f}s — may have hung"
            assert "timeout" in str(exc_info.value).lower() or "overflow" in str(exc_info.value).lower() or "QueuePool" in str(exc_info.value)
        finally:
            for conn in held_connections:
                conn.close()

    def test_release_connection_allows_next_acquire(self, tight_pool_engine):
        """After exhaustion, releasing a connection makes pool usable."""
        engine = tight_pool_engine
        held_connections = []

        try:
            # Exhaust pool
            for _ in range(3):
                conn = engine.connect()
                held_connections.append(conn)

            # Release one
            held_connections[0].close()
            held_connections.pop(0)

            # Should now be able to acquire
            new_conn = engine.connect()
            result = new_conn.execute(text("SELECT 1"))
            assert result.scalar() == 1
            new_conn.close()
        finally:
            for conn in held_connections:
                conn.close()

    def test_concurrent_pool_exhaustion_no_deadlock(self, tight_pool_engine):
        """Many threads competing for small pool — no deadlock, all eventually complete or timeout."""
        engine = tight_pool_engine
        results = {"success": 0, "timeout": 0, "error": 0}
        lock = threading.Lock()

        def worker():
            try:
                with engine.connect() as conn:
                    conn.execute(text("SELECT pg_sleep(0.1)"))
                    with lock:
                        results["success"] += 1
            except Exception as e:
                err_str = str(e).lower()
                with lock:
                    if "timeout" in err_str or "queuepool" in err_str or "overflow" in err_str:
                        results["timeout"] += 1
                    else:
                        results["error"] += 1

        threads = [threading.Thread(target=worker) for _ in range(20)]
        start = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        elapsed = time.perf_counter() - start

        # All threads must complete (no deadlock/hang)
        assert elapsed < 30, f"Threads took {elapsed:.1f}s — likely deadlocked"
        # Some should succeed, some may timeout — but no unexpected errors
        assert results["error"] == 0, f"Unexpected errors: {results}"
        assert results["success"] > 0, f"No successful connections: {results}"


class TestConcurrentPoolAccess:
    """High-concurrency pool access patterns."""

    def test_100_concurrent_sessions_complete(self, medium_pool_engine):
        """100 concurrent get_session() calls with pool_size=10 all complete within 10s."""
        Session = sessionmaker(bind=medium_pool_engine)
        results = {"success": 0, "error": 0}
        errors = []
        lock = threading.Lock()

        def worker(i):
            try:
                session = Session()
                session.execute(text("SELECT 1"))
                session.close()
                with lock:
                    results["success"] += 1
            except Exception as e:
                with lock:
                    results["error"] += 1
                    errors.append(str(e))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(100)]
        start = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        elapsed = time.perf_counter() - start

        assert elapsed < 10, f"100 sessions took {elapsed:.1f}s (budget: 10s)"
        assert results["success"] == 100, f"Only {results['success']}/100 succeeded. Errors: {errors[:3]}"

    def test_rapid_acquire_release_cycle(self, medium_pool_engine):
        """Rapidly acquiring and releasing connections doesn't leak."""
        for i in range(200):
            with medium_pool_engine.connect() as conn:
                conn.execute(text("SELECT 1"))

        # If we get here without error, connections were properly returned
        # Verify pool status
        pool = medium_pool_engine.pool
        assert pool.checkedout() == 0, f"Leaked connections: {pool.checkedout()} checked out"

    def test_mixed_fast_slow_queries(self, medium_pool_engine):
        """Mix of fast and slow queries doesn't starve fast queries."""
        Session = sessionmaker(bind=medium_pool_engine)
        fast_times = []
        lock = threading.Lock()

        def slow_worker():
            session = Session()
            session.execute(text("SELECT pg_sleep(0.5)"))
            session.close()

        def fast_worker():
            start = time.perf_counter()
            session = Session()
            session.execute(text("SELECT 1"))
            session.close()
            elapsed = time.perf_counter() - start
            with lock:
                fast_times.append(elapsed)

        # Launch 5 slow + 20 fast queries
        slow_threads = [threading.Thread(target=slow_worker) for _ in range(5)]
        fast_threads = [threading.Thread(target=fast_worker) for _ in range(20)]

        for t in slow_threads:
            t.start()
        time.sleep(0.05)  # Let slow queries start first
        for t in fast_threads:
            t.start()

        for t in slow_threads + fast_threads:
            t.join(timeout=15)

        # Fast queries should complete reasonably quickly despite slow queries holding connections
        assert len(fast_times) == 20, f"Only {len(fast_times)}/20 fast queries completed"
        avg_fast = sum(fast_times) / len(fast_times)
        assert avg_fast < 2.0, f"Fast queries averaged {avg_fast:.3f}s — starved by slow queries"
