"""Category F.4: Unicode and special character tests on PostgreSQL."""

import pytest
from sqlalchemy import text

from intellibox.models import Base, Email, Settings
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


class TestUnicodeEncoding:
    """Unicode and special characters in all text fields."""

    @pytest.mark.parametrize("subject", [
        "Meeting about caf\u00e9 r\u00e9sum\u00e9",  # French accents
        "\u65e5\u672c\u8a9e\u30c6\u30b9\u30c8",  # Japanese
        "\U0001f680 Launch Day \U0001f389",  # Emoji
        "Hello \u200b\u200b World",  # Zero-width spaces
        "Subject with 'quotes' and \"double quotes\"",
        "Very long " + "x" * 5000,  # 5K chars
        "Tab\there\nnewline\rtoo",  # Whitespace chars
        "Backslash \\ and slash /",
    ])
    def test_unicode_email_subject(self, subject):
        """Various unicode strings survive round-trip in email subject."""
        session = PgSessionLocal()
        email = Email(
            message_id=f"unicode-{hash(subject)}@test.com",
            subject=subject,
            from_address="a@b.com",
            to_addresses="[]",
            received_date=utcnow(),
            created_at=utcnow(),
        )
        session.add(email)
        session.commit()
        fetched = session.query(Email).get(email.id)
        assert fetched.subject == subject
        session.close()

    def test_unicode_in_body_text(self):
        """Unicode in body_text field."""
        session = PgSessionLocal()
        body = "Caf\u00e9 \U0001f600 \u65e5\u672c\u8a9e \u0410\u0411\u0412"
        email = Email(
            message_id="body-unicode@test.com",
            subject="Test", from_address="a@b.com",
            to_addresses="[]", received_date=utcnow(),
            created_at=utcnow(), body_text=body,
        )
        session.add(email)
        session.commit()
        fetched = session.query(Email).get(email.id)
        assert fetched.body_text == body
        session.close()

    def test_unicode_in_settings(self):
        """Unicode in settings value."""
        session = PgSessionLocal()
        value = '"\U0001f680 Rocket \u2603 Snowman"'
        s = Settings(key="unicode_test", value=value, updated_at=utcnow())
        session.add(s)
        session.commit()
        fetched = session.query(Settings).filter_by(key="unicode_test").first()
        assert fetched.value == value
        session.close()

    def test_large_text_field(self):
        """10KB text field stored and retrieved correctly."""
        session = PgSessionLocal()
        big_text = "A" * 10240
        email = Email(
            message_id="big-body@test.com",
            subject="Test", from_address="a@b.com",
            to_addresses="[]", received_date=utcnow(),
            created_at=utcnow(), body_text=big_text,
        )
        session.add(email)
        session.commit()
        fetched = session.query(Email).get(email.id)
        assert len(fetched.body_text) == 10240
        session.close()
