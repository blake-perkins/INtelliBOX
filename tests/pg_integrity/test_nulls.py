"""Category F.5: NULL handling consistency on PostgreSQL."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from intellibox.models import Base, Email
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


class TestNullHandling:
    """NULL values are stored and retrieved correctly."""

    def test_nullable_fields_store_none(self):
        """All nullable columns correctly store and return None."""
        session = PgSessionLocal()
        email = Email(
            message_id="null-test@test.com",
            subject="Null test",
            from_address="a@b.com",
            to_addresses="[]",
            received_date=utcnow(),
            created_at=utcnow(),
            # All optional fields left as None:
            from_name=None,
            cc_addresses=None,
            body_text=None,
            body_html=None,
            raw_eml_path=None,
            also_received_from=None,
            processed_at=None,
        )
        session.add(email)
        session.commit()

        fetched = session.query(Email).get(email.id)
        assert fetched.from_name is None
        assert fetched.cc_addresses is None
        assert fetched.body_text is None
        assert fetched.body_html is None
        assert fetched.raw_eml_path is None
        assert fetched.also_received_from is None
        assert fetched.processed_at is None
        session.close()

    def test_non_nullable_subject_rejects_none(self):
        """Non-nullable 'subject' column rejects None."""
        session = PgSessionLocal()
        email = Email(
            message_id="no-subject@test.com",
            subject=None,  # Should fail
            from_address="a@b.com",
            to_addresses="[]",
            received_date=utcnow(),
            created_at=utcnow(),
        )
        session.add(email)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        session.close()

    def test_non_nullable_message_id_rejects_none(self):
        """Non-nullable 'message_id' column rejects None."""
        session = PgSessionLocal()
        email = Email(
            message_id=None,  # Should fail
            subject="Test",
            from_address="a@b.com",
            to_addresses="[]",
            received_date=utcnow(),
            created_at=utcnow(),
        )
        session.add(email)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        session.close()

    def test_null_not_equal_to_empty_string(self):
        """NULL and empty string are distinct in PostgreSQL."""
        session = PgSessionLocal()
        email_null = Email(
            message_id="null-body@test.com",
            subject="Null", from_address="a@b.com",
            to_addresses="[]", received_date=utcnow(),
            created_at=utcnow(), body_text=None,
        )
        email_empty = Email(
            message_id="empty-body@test.com",
            subject="Empty", from_address="a@b.com",
            to_addresses="[]", received_date=utcnow(),
            created_at=utcnow(), body_text="",
        )
        session.add_all([email_null, email_empty])
        session.commit()

        null_email = session.query(Email).filter_by(message_id="null-body@test.com").first()
        empty_email = session.query(Email).filter_by(message_id="empty-body@test.com").first()
        assert null_email.body_text is None
        assert empty_email.body_text == ""
        assert null_email.body_text != empty_email.body_text
        session.close()
