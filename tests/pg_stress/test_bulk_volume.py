"""Category D.3: Large data volume tests on PostgreSQL."""

import time

import pytest

from intellibox.models import Action, Email
from intellibox.utils.datetime_utils import utcnow
from tests.pg_stress.conftest import StressSessionLocal

pytestmark = [pytest.mark.pg, pytest.mark.stress]


class TestBulkVolume:
    """Performance with large data sets."""

    def test_10k_emails_query_performance(self, stress_setup):
        """Insert 10K emails + 20K actions, query dashboard stats within 500ms."""
        session = StressSessionLocal()
        for i in range(10000):
            email = Email(
                message_id=f"vol-{i}@test.com",
                subject=f"Volume email {i}",
                from_address="vol@test.com",
                to_addresses="[]",
                received_date=utcnow(),
                created_at=utcnow(),
            )
            session.add(email)
            if i % 1000 == 0:
                session.flush()
        session.commit()

        # Add actions (2 per email for first 10K)
        for i in range(10000):
            email = session.query(Email).filter_by(
                message_id=f"vol-{i}@test.com"
            ).first()
            for j in range(2):
                action = Action(
                    email_id=email.id,
                    title=f"Action {i}-{j}",
                    priority=["high", "medium", "low"][j % 3],
                    created_at=utcnow(),
                )
                session.add(action)
            if i % 1000 == 0:
                session.flush()
        session.commit()

        # Dashboard stats query
        start = time.monotonic()
        total_emails = session.query(Email).count()
        total_actions = session.query(Action).count()
        elapsed = time.monotonic() - start

        assert total_emails == 10000
        assert total_actions == 20000
        assert elapsed < 0.5, f"Dashboard query took {elapsed:.3f}s (limit: 0.5s)"
        session.close()

    def test_paginated_actions_query(self, stress_setup):
        """Paginated action list query within 200ms per page."""
        # Seed 1000 actions
        session = StressSessionLocal()
        email = Email(
            message_id="paginate@test.com",
            subject="Paginate test",
            from_address="p@test.com",
            to_addresses="[]",
            received_date=utcnow(),
            created_at=utcnow(),
        )
        session.add(email)
        session.flush()

        for i in range(1000):
            action = Action(
                email_id=email.id,
                title=f"Page action {i}",
                priority=["high", "medium", "low"][i % 3],
                created_at=utcnow(),
            )
            session.add(action)
        session.commit()

        # Paginated query
        start = time.monotonic()
        page = session.query(Action).order_by(Action.id).limit(50).offset(500).all()
        elapsed = time.monotonic() - start

        assert len(page) == 50
        assert elapsed < 0.2, f"Paginated query took {elapsed:.3f}s (limit: 0.2s)"
        session.close()
