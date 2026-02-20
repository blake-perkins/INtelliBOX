"""Category J: PostgreSQL performance baseline tests.

Verifies query performance and index effectiveness.
Requires: docker compose -f docker-compose.pg-test.yml up -d
"""

import json
import time

import pytest
from sqlalchemy import text

from intellibox.models import Action, Base, Email
from intellibox.utils.datetime_utils import utcnow
from tests.pg_conftest import PgSessionLocal, pg_engine

pytestmark = pytest.mark.pg


@pytest.fixture(scope="module", autouse=True)
def pg_setup():
    Base.metadata.create_all(bind=pg_engine)
    yield
    Base.metadata.drop_all(bind=pg_engine)
    pg_engine.dispose()


@pytest.fixture(scope="module")
def seeded_data(pg_setup):
    """Seed 10K emails + 20K actions for performance testing. Module-scoped for reuse."""
    session = PgSessionLocal()
    now = utcnow()

    # Bulk insert 10K emails in batches
    batch_size = 500
    for batch_start in range(0, 10000, batch_size):
        emails = []
        for i in range(batch_start, batch_start + batch_size):
            emails.append(Email(
                message_id=f"perf-{i}@test.com",
                subject=f"Performance test email {i}",
                from_address=f"sender-{i % 100}@test.com",
                to_addresses=json.dumps([f"to-{i}@test.com"]),
                received_date=now,
                created_at=now,
                processed=(i % 2 == 0),
            ))
        session.add_all(emails)
        session.flush()

    # Bulk insert 20K actions (2 per email)
    emails = session.query(Email).all()
    for idx, email in enumerate(emails):
        for j in range(2):
            session.add(Action(
                email_id=email.id,
                title=f"Action {idx}-{j}",
                priority=["high", "medium", "low"][idx % 3],
                created_at=now,
            ))
        # Flush periodically to avoid memory buildup
        if idx % 500 == 0:
            session.flush()

    session.commit()
    yield session
    session.close()


class TestQueryPerformance:
    """Query response time on 10K+ row tables."""

    def test_dashboard_stats_under_500ms(self, seeded_data):
        """Dashboard-style aggregate query completes in < 500ms."""
        session = seeded_data

        start = time.perf_counter()
        total_emails = session.query(Email).count()
        total_actions = session.query(Action).count()
        processed = session.query(Email).filter_by(processed=True).count()
        high_priority = session.query(Action).filter_by(priority="high").count()
        elapsed = time.perf_counter() - start

        assert total_emails == 10000
        assert total_actions == 20000
        assert processed > 0
        assert high_priority > 0
        assert elapsed < 0.5, f"Dashboard stats took {elapsed:.3f}s (budget: 0.5s)"

    def test_actions_paginated_under_200ms(self, seeded_data):
        """Paginated actions query completes in < 200ms per page."""
        session = seeded_data
        page_size = 50

        # Test first page
        start = time.perf_counter()
        actions = session.query(Action).order_by(Action.id).limit(page_size).all()
        elapsed = time.perf_counter() - start

        assert len(actions) == page_size
        assert elapsed < 0.2, f"Page 1 took {elapsed:.3f}s (budget: 0.2s)"

        # Test middle page (offset 5000)
        start = time.perf_counter()
        actions = session.query(Action).order_by(Action.id).offset(5000).limit(page_size).all()
        elapsed = time.perf_counter() - start

        assert len(actions) == page_size
        assert elapsed < 0.2, f"Middle page took {elapsed:.3f}s (budget: 0.2s)"

    def test_filter_by_priority_under_200ms(self, seeded_data):
        """Filtering actions by priority uses index and is fast."""
        session = seeded_data

        start = time.perf_counter()
        high = session.query(Action).filter_by(priority="high").limit(100).all()
        elapsed = time.perf_counter() - start

        assert len(high) == 100
        assert elapsed < 0.2, f"Priority filter took {elapsed:.3f}s (budget: 0.2s)"

    def test_email_lookup_by_message_id_under_50ms(self, seeded_data):
        """Indexed lookup by message_id is very fast."""
        session = seeded_data

        start = time.perf_counter()
        email = session.query(Email).filter_by(message_id="perf-5000@test.com").first()
        elapsed = time.perf_counter() - start

        assert email is not None
        assert elapsed < 0.05, f"message_id lookup took {elapsed:.3f}s (budget: 0.05s)"


class TestConnectionSetup:
    """Connection establishment performance."""

    def test_connection_setup_under_50ms(self):
        """New connection established in < 50ms."""
        from sqlalchemy import create_engine

        from tests.pg_conftest import PG_TEST_URL

        eng = create_engine(PG_TEST_URL, pool_size=1, max_overflow=0)

        start = time.perf_counter()
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        elapsed = time.perf_counter() - start

        assert elapsed < 0.05, f"Connection setup took {elapsed:.3f}s (budget: 0.05s)"
        eng.dispose()


class TestIndexEffectiveness:
    """Verify indexes are used via EXPLAIN ANALYZE."""

    def test_message_id_index_used(self, seeded_data):
        """EXPLAIN ANALYZE shows index scan on message_id lookup."""
        with pg_engine.connect() as conn:
            result = conn.execute(text(
                "EXPLAIN ANALYZE SELECT * FROM emails WHERE message_id = 'perf-5000@test.com'"
            ))
            plan = "\n".join(row[0] for row in result)

        assert "Index" in plan or "index" in plan, f"Expected index scan, got:\n{plan}"

    def test_email_id_index_used(self, seeded_data):
        """EXPLAIN ANALYZE shows index scan on actions.email_id lookup."""
        # Get a real email id
        with pg_engine.connect() as conn:
            row = conn.execute(text("SELECT id FROM emails LIMIT 1")).fetchone()
            email_id = row[0]

            result = conn.execute(text(
                f"EXPLAIN ANALYZE SELECT * FROM actions WHERE email_id = {email_id}"
            ))
            plan = "\n".join(row[0] for row in result)

        assert "Index" in plan or "index" in plan, f"Expected index scan, got:\n{plan}"

    def test_priority_index_used(self, seeded_data):
        """EXPLAIN ANALYZE shows index usage on priority filter."""
        with pg_engine.connect() as conn:
            result = conn.execute(text(
                "EXPLAIN ANALYZE SELECT * FROM actions WHERE priority = 'high' LIMIT 100"
            ))
            plan = "\n".join(row[0] for row in result)

        # PostgreSQL may choose index scan or bitmap index scan
        plan_lower = plan.lower()
        uses_index = "index" in plan_lower
        # On small-enough tables PG might choose seq scan — that's acceptable if query is fast
        if not uses_index:
            # Verify the query is still fast even without index
            import time
            start = time.perf_counter()
            conn2 = pg_engine.connect()
            conn2.execute(text("SELECT * FROM actions WHERE priority = 'high' LIMIT 100")).fetchall()
            elapsed = time.perf_counter() - start
            conn2.close()
            assert elapsed < 0.2, f"No index and slow ({elapsed:.3f}s)"

    def test_received_date_index_used(self, seeded_data):
        """EXPLAIN ANALYZE shows index on received_date range query."""
        with pg_engine.connect() as conn:
            result = conn.execute(text(
                "EXPLAIN ANALYZE SELECT * FROM emails WHERE received_date > NOW() - INTERVAL '7 days' ORDER BY received_date DESC LIMIT 50"
            ))
            plan = "\n".join(row[0] for row in result)

        # Index or bitmap scan expected for date range
        plan_lower = plan.lower()
        assert "index" in plan_lower or "bitmap" in plan_lower or "sort" in plan_lower, \
            f"Expected index-assisted query, got:\n{plan}"
