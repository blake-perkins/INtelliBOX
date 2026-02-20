"""Category H.2-H.3: Malformed JSON and oversized payload tests on PostgreSQL."""

import json

import pytest
from sqlalchemy import text

from intellibox.models import Base, Email, KnowledgeDocument, Settings
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


class TestMalformedJSON:
    """Invalid JSON in TEXT columns doesn't crash the database."""

    def test_malformed_json_in_to_addresses(self):
        """Storing invalid JSON in to_addresses is allowed (it's just TEXT)."""
        session = PgSessionLocal()
        email = Email(
            message_id="badjson@test.com",
            subject="Test",
            from_address="a@b.com",
            to_addresses="not valid json {{",
            received_date=utcnow(),
            created_at=utcnow(),
        )
        session.add(email)
        session.commit()

        fetched = session.query(Email).get(email.id)
        assert fetched.to_addresses == "not valid json {{"
        session.close()

    def test_malformed_json_in_settings(self):
        """Invalid JSON in settings.value is stored and retrievable."""
        session = PgSessionLocal()
        setting = Settings(key="broken_json", value="{not json", updated_at=utcnow())
        session.add(setting)
        session.commit()

        fetched = session.query(Settings).filter_by(key="broken_json").first()
        assert fetched.value == "{not json"
        # json.loads should fail but the value is accessible
        with pytest.raises(json.JSONDecodeError):
            json.loads(fetched.value)
        session.close()


class TestOversizedPayloads:
    """Large data stored and retrieved correctly."""

    def test_1mb_email_body(self):
        """Email with 1MB body text is stored and retrieved."""
        session = PgSessionLocal()
        body = "x" * (1024 * 1024)
        email = Email(
            message_id="bigbody@test.com",
            subject="Big body",
            from_address="a@b.com",
            to_addresses="[]",
            received_date=utcnow(),
            created_at=utcnow(),
            body_text=body,
        )
        session.add(email)
        session.commit()

        fetched = session.query(Email).get(email.id)
        assert len(fetched.body_text) == 1024 * 1024
        session.close()

    def test_10k_subject(self):
        """Subject exceeding 10K characters is stored."""
        session = PgSessionLocal()
        subject = "S" * 10000
        email = Email(
            message_id="bigsubj@test.com",
            subject=subject,
            from_address="a@b.com",
            to_addresses="[]",
            received_date=utcnow(),
            created_at=utcnow(),
        )
        session.add(email)
        session.commit()

        fetched = session.query(Email).get(email.id)
        assert len(fetched.subject) == 10000
        session.close()

    def test_100k_settings_value(self):
        """Settings value with 100K characters round-trips."""
        session = PgSessionLocal()
        big_json = json.dumps({"data": "x" * 100000})
        setting = Settings(key="big_setting", value=big_json, updated_at=utcnow())
        session.add(setting)
        session.commit()

        fetched = session.query(Settings).filter_by(key="big_setting").first()
        assert fetched.value == big_json
        parsed = json.loads(fetched.value)
        assert len(parsed["data"]) == 100000
        session.close()

    def test_large_extracted_text(self):
        """Knowledge document with large extracted_text."""
        session = PgSessionLocal()
        big_text = "Document content " * 10000
        doc = KnowledgeDocument(
            filename="big.txt", file_type="txt", file_size=len(big_text),
            extracted_text=big_text, uploaded_at=utcnow(),
        )
        session.add(doc)
        session.commit()

        fetched = session.query(KnowledgeDocument).get(doc.id)
        assert fetched.extracted_text == big_text
        session.close()
