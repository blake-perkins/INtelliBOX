"""Category D.1: Concurrent read/write stress tests on PostgreSQL."""

import json
import threading
import time

import pytest

from intellibox.models import Action, Email
from intellibox.utils.datetime_utils import utcnow
from tests.pg_stress.conftest import StressSessionLocal

pytestmark = [pytest.mark.pg, pytest.mark.stress]


class TestConcurrentReadWrite:
    """High-throughput concurrent access tests."""

    def test_100_concurrent_writers(self, stress_setup):
        """100 threads each insert an Email+Action — all succeed, zero deadlocks."""
        errors = []
        ids = []
        lock = threading.Lock()

        def writer(i):
            session = StressSessionLocal()
            try:
                email = Email(
                    message_id=f"stress-{i}@test.com",
                    subject=f"Stress email {i}",
                    from_address="stress@test.com",
                    to_addresses=json.dumps([f"r{i}@test.com"]),
                    received_date=utcnow(),
                    created_at=utcnow(),
                )
                session.add(email)
                session.flush()
                action = Action(
                    email_id=email.id,
                    title=f"Stress action {i}",
                    priority="medium",
                    created_at=utcnow(),
                )
                session.add(action)
                session.commit()
                with lock:
                    ids.append(email.id)
            except Exception as e:
                session.rollback()
                with lock:
                    errors.append((i, str(e)))
            finally:
                session.close()

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(100)]
        start = time.monotonic()
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        elapsed = time.monotonic() - start

        assert len(errors) == 0, f"Errors: {errors[:5]}"
        assert len(ids) == 100, f"Only {len(ids)}/100 succeeded"
        print(f"100 concurrent inserts completed in {elapsed:.2f}s")

    def test_50_writers_50_readers(self, stress_setup):
        """50 writers + 50 readers simultaneously — zero errors."""
        # Pre-seed some data for readers
        session = StressSessionLocal()
        for i in range(20):
            email = Email(
                message_id=f"seed-{i}@test.com",
                subject=f"Seed {i}",
                from_address="seed@test.com",
                to_addresses="[]",
                received_date=utcnow(),
                created_at=utcnow(),
            )
            session.add(email)
        session.commit()
        session.close()

        errors = []
        lock = threading.Lock()

        def writer(i):
            s = StressSessionLocal()
            try:
                email = Email(
                    message_id=f"rw-write-{i}@test.com",
                    subject=f"Written {i}",
                    from_address="w@test.com",
                    to_addresses="[]",
                    received_date=utcnow(),
                    created_at=utcnow(),
                )
                s.add(email)
                s.commit()
            except Exception as e:
                s.rollback()
                with lock:
                    errors.append(("writer", i, str(e)))
            finally:
                s.close()

        def reader(i):
            s = StressSessionLocal()
            try:
                emails = s.query(Email).limit(10).all()
                assert len(emails) >= 0  # Just verify no crash
            except Exception as e:
                with lock:
                    errors.append(("reader", i, str(e)))
            finally:
                s.close()

        threads = []
        for i in range(50):
            threads.append(threading.Thread(target=writer, args=(i,)))
            threads.append(threading.Thread(target=reader, args=(i,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert len(errors) == 0, f"Errors: {errors[:5]}"

    def test_rapid_sequential_inserts(self, stress_setup):
        """5,000 emails inserted rapidly — throughput > 200/second."""
        session = StressSessionLocal()
        start = time.monotonic()
        for i in range(5000):
            email = Email(
                message_id=f"rapid-{i}@test.com",
                subject=f"Rapid {i}",
                from_address="rapid@test.com",
                to_addresses="[]",
                received_date=utcnow(),
                created_at=utcnow(),
            )
            session.add(email)
            if i % 500 == 0:
                session.flush()
        session.commit()
        elapsed = time.monotonic() - start
        session.close()

        throughput = 5000 / elapsed
        print(f"5000 inserts in {elapsed:.2f}s ({throughput:.0f}/sec)")
        assert throughput > 200, f"Throughput {throughput:.0f}/sec below 200/sec threshold"
