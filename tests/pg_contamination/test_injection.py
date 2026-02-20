"""Category H.1: SQL injection tests on PostgreSQL.

Verifies that SQLAlchemy ORM parameterized queries prevent injection.
"""


import pytest
from sqlalchemy import text

from intellibox.models import Base, Email, RosterMember, Settings
from intellibox.utils.datetime_utils import utcnow
from tests.pg_conftest import PgSessionLocal, pg_engine

pytestmark = pytest.mark.pg

INJECTION_PAYLOADS = [
    "'; DROP TABLE emails; --",
    "' OR '1'='1",
    "Robert'); DROP TABLE actions;--",
    "' UNION SELECT * FROM settings--",
    '"; TRUNCATE emails CASCADE; --',
    "1; SELECT pg_sleep(10);--",
    "\\x00\\x01\\x02",
    "' AND 1=1 UNION SELECT NULL,NULL,NULL--",
]


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


class TestSQLInjection:
    """All injection payloads stored as data, never executed."""

    @pytest.mark.parametrize("payload", INJECTION_PAYLOADS)
    def test_injection_via_email_subject(self, payload):
        """SQL injection in email subject does not execute."""
        session = PgSessionLocal()
        email = Email(
            message_id=f"inj-{hash(payload)}@test.com",
            subject=payload,
            from_address="a@b.com",
            to_addresses="[]",
            received_date=utcnow(),
            created_at=utcnow(),
        )
        session.add(email)
        session.commit()

        # Verify stored as data
        fetched = session.query(Email).get(email.id)
        assert fetched.subject == payload

        # Verify no tables were dropped
        from sqlalchemy import inspect
        inspector = inspect(pg_engine)
        tables = inspector.get_table_names()
        assert "emails" in tables
        assert "actions" in tables
        session.close()

    @pytest.mark.parametrize("payload", INJECTION_PAYLOADS)
    def test_injection_via_settings_value(self, payload):
        """SQL injection in settings value does not execute."""
        session = PgSessionLocal()
        key = f"inj_{abs(hash(payload)) % 1000}"
        setting = Settings(key=key, value=payload, updated_at=utcnow())
        session.add(setting)
        session.commit()

        fetched = session.query(Settings).filter_by(key=key).first()
        assert fetched.value == payload
        session.close()

    @pytest.mark.parametrize("payload", INJECTION_PAYLOADS)
    def test_injection_via_roster_fields(self, payload):
        """SQL injection in roster fields does not execute."""
        session = PgSessionLocal()
        member = RosterMember(
            first_name=payload[:100],
            last_name=payload[:100],
            email=f"inj-{abs(hash(payload)) % 10000}@test.com",
            created_at=utcnow(),
        )
        session.add(member)
        session.commit()

        fetched = session.query(RosterMember).get(member.id)
        assert fetched.first_name == payload[:100]
        session.close()
