"""Category F.1: Transaction isolation tests on PostgreSQL."""

import threading

import pytest
from sqlalchemy import text

from intellibox.models import Action, Assignment, Base, Email
from intellibox.utils.datetime_utils import utcnow
from tests.pg_conftest import PgSessionLocal, pg_engine

pytestmark = pytest.mark.pg


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


class TestTransactionIsolation:
    """Concurrent writes maintain data integrity."""

    def test_concurrent_assignment_no_crash(self):
        """Two threads assigning the same action don't crash."""
        session = PgSessionLocal()
        email = Email(
            message_id="iso-test@test.com", subject="T",
            from_address="a@b.com", to_addresses="[]",
            received_date=utcnow(), created_at=utcnow(),
        )
        session.add(email)
        session.flush()
        action = Action(email_id=email.id, title="Contested", created_at=utcnow())
        session.add(action)
        session.commit()
        action_id = action.id
        session.close()

        errors = []

        def assign(name):
            s = PgSessionLocal()
            try:
                a = Assignment(
                    action_id=action_id, assigned_to=name,
                    status="assigned", assigned_at=utcnow(),
                )
                s.add(a)
                s.commit()
            except Exception as e:
                s.rollback()
                errors.append(e)
            finally:
                s.close()

        t1 = threading.Thread(target=assign, args=("Alice",))
        t2 = threading.Thread(target=assign, args=("Bob",))
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        # Both should succeed (no unique constraint on assignments)
        s = PgSessionLocal()
        count = s.query(Assignment).filter_by(action_id=action_id).count()
        s.close()
        assert count == 2  # Both inserts succeed

    def test_uncommitted_changes_not_visible(self):
        """Changes in one session are not visible in another until committed."""
        s1 = PgSessionLocal()
        s2 = PgSessionLocal()

        email = Email(
            message_id="visibility@test.com", subject="Invisible",
            from_address="a@b.com", to_addresses="[]",
            received_date=utcnow(), created_at=utcnow(),
        )
        s1.add(email)
        s1.flush()  # Not committed yet

        # s2 should NOT see the uncommitted email
        count = s2.query(Email).filter_by(message_id="visibility@test.com").count()
        assert count == 0

        s1.commit()
        s1.close()
        s2.close()

    def test_rollback_removes_all_data(self):
        """After rollback, no partial data persists."""
        session = PgSessionLocal()
        email = Email(
            message_id="rollback@test.com", subject="Gone",
            from_address="a@b.com", to_addresses="[]",
            received_date=utcnow(), created_at=utcnow(),
        )
        session.add(email)
        session.flush()
        session.rollback()

        # In a new session, the email should not exist
        s2 = PgSessionLocal()
        count = s2.query(Email).filter_by(message_id="rollback@test.com").count()
        assert count == 0
        s2.close()
        session.close()
