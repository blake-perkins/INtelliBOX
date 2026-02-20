"""Category I: SQLite to PostgreSQL data migration tests.

Tests the data migration script's accuracy.
Requires: docker compose -f docker-compose.pg-test.yml up -d
"""

import json
import tempfile

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from intellibox.models import (
    Action,
    Base,
    Email,
    KnowledgeChunk,
    KnowledgeDocument,
    RosterMember,
    Settings,
)
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


def _create_sqlite_with_data():
    """Create a temp SQLite database with test data. Returns (engine, url, expected_counts)."""
    import os
    fd, path = tempfile.mkstemp(suffix="_migrate.db")
    os.close(fd)
    url = f"sqlite:///{path}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    now = utcnow()
    emails = []
    for i in range(5):
        email = Email(
            message_id=f"migrate-{i}@test.com",
            subject=f"Migration email {i}",
            from_address="migrate@test.com",
            to_addresses=json.dumps([f"to-{i}@test.com"]),
            received_date=now,
            created_at=now,
        )
        session.add(email)
        session.flush()
        emails.append(email)

        action = Action(
            email_id=email.id,
            title=f"Action {i}",
            priority=["high", "medium", "low"][i % 3],
            created_at=now,
        )
        session.add(action)

    session.add(Settings(key="migrate_test", value=json.dumps([1, 2, 3]), updated_at=now))
    session.add(RosterMember(
        first_name="Test", last_name="User",
        email="test@migrate.com", created_at=now,
    ))

    doc = KnowledgeDocument(
        filename="test.txt", file_type="txt", file_size=100,
        extracted_text="Test document text", uploaded_at=now,
    )
    session.add(doc)
    session.flush()
    session.add(KnowledgeChunk(
        document_id=doc.id, chunk_index=0, chunk_text="chunk text",
        embedding=json.dumps([0.1] * 10),
    ))

    session.commit()

    counts = {
        "emails": session.query(Email).count(),
        "actions": session.query(Action).count(),
        "settings": session.query(Settings).count(),
        "roster": session.query(RosterMember).count(),
        "knowledge_documents": session.query(KnowledgeDocument).count(),
        "knowledge_chunks": session.query(KnowledgeChunk).count(),
    }
    session.close()
    return engine, url, path, counts


class TestDataMigration:
    """SQLite to PostgreSQL data transfer accuracy."""

    def test_manual_migration_preserves_data(self):
        """Manually migrated data matches source."""
        sqlite_engine, sqlite_url, sqlite_path, expected = _create_sqlite_with_data()
        SqliteSession = sessionmaker(bind=sqlite_engine)

        # Read all data from SQLite
        ss = SqliteSession()
        sqlite_emails = ss.query(Email).all()
        sqlite_actions = ss.query(Action).all()
        sqlite_settings = ss.query(Settings).all()
        sqlite_roster = ss.query(RosterMember).all()
        sqlite_docs = ss.query(KnowledgeDocument).all()
        sqlite_chunks = ss.query(KnowledgeChunk).all()
        ss.close()

        # Insert into PostgreSQL
        pg_session = PgSessionLocal()
        for e in sqlite_emails:
            pg_session.add(Email(
                message_id=e.message_id, subject=e.subject,
                from_address=e.from_address, to_addresses=e.to_addresses,
                received_date=e.received_date, created_at=e.created_at,
                processed=e.processed,
            ))
        pg_session.flush()

        # Map old email IDs to new ones by message_id
        id_map = {}
        for e in sqlite_emails:
            pg_email = pg_session.query(Email).filter_by(message_id=e.message_id).first()
            id_map[e.id] = pg_email.id

        for a in sqlite_actions:
            pg_session.add(Action(
                email_id=id_map[a.email_id], title=a.title,
                priority=a.priority, created_at=a.created_at,
            ))

        for s in sqlite_settings:
            pg_session.add(Settings(
                key=s.key, value=s.value,
                description=s.description, updated_at=s.updated_at,
            ))

        for r in sqlite_roster:
            pg_session.add(RosterMember(
                first_name=r.first_name, last_name=r.last_name,
                email=r.email, created_at=r.created_at,
            ))

        for d in sqlite_docs:
            pg_session.add(KnowledgeDocument(
                filename=d.filename, file_type=d.file_type,
                file_size=d.file_size, extracted_text=d.extracted_text,
                uploaded_at=d.uploaded_at,
            ))
        pg_session.flush()

        pg_doc = pg_session.query(KnowledgeDocument).first()
        for c in sqlite_chunks:
            pg_session.add(KnowledgeChunk(
                document_id=pg_doc.id, chunk_index=c.chunk_index,
                chunk_text=c.chunk_text, embedding=c.embedding,
            ))

        pg_session.commit()

        # Verify counts
        assert pg_session.query(Email).count() == expected["emails"]
        assert pg_session.query(Action).count() == expected["actions"]
        assert pg_session.query(Settings).count() == expected["settings"]
        assert pg_session.query(RosterMember).count() == expected["roster"]
        assert pg_session.query(KnowledgeDocument).count() == expected["knowledge_documents"]
        assert pg_session.query(KnowledgeChunk).count() == expected["knowledge_chunks"]

        # Verify specific data
        pg_email = pg_session.query(Email).filter_by(message_id="migrate-0@test.com").first()
        assert pg_email is not None
        assert json.loads(pg_email.to_addresses) == ["to-0@test.com"]

        pg_setting = pg_session.query(Settings).filter_by(key="migrate_test").first()
        assert json.loads(pg_setting.value) == [1, 2, 3]

        pg_chunk = pg_session.query(KnowledgeChunk).first()
        assert json.loads(pg_chunk.embedding) == [0.1] * 10

        pg_session.close()

        # Cleanup SQLite
        sqlite_engine.dispose()
        import os
        os.unlink(sqlite_path)

    def test_new_inserts_after_migration_get_correct_ids(self):
        """After importing data, new inserts get IDs beyond the imported range."""
        pg_session = PgSessionLocal()
        # Insert with explicit IDs via raw SQL to simulate migration
        with pg_engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO emails (id, message_id, subject, from_address, to_addresses, received_date, created_at, processed)
                VALUES (100, 'seq-test@test.com', 'Seq', 'a@b.com', '[]', NOW(), NOW(), false)
            """))
            # Reset sequence to max(id) + 1
            conn.execute(text("SELECT setval('emails_id_seq', (SELECT COALESCE(MAX(id), 0) FROM emails))"))
            conn.commit()

        # New insert should get id > 100
        email = Email(
            message_id="after-seq@test.com",
            subject="After migration",
            from_address="a@b.com",
            to_addresses="[]",
            received_date=utcnow(),
            created_at=utcnow(),
        )
        pg_session.add(email)
        pg_session.commit()
        assert email.id > 100, f"Expected id > 100, got {email.id}"
        pg_session.close()
