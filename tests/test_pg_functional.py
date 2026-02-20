"""Category A: Functional correctness on PostgreSQL.

Verifies that all ORM operations work identically on PostgreSQL as on SQLite.
Requires: docker compose -f docker-compose.pg-test.yml up -d
"""

import json

import pytest
from sqlalchemy.exc import IntegrityError

from intellibox.models import (
    Action,
    Assignment,
    Base,
    Email,
    KnowledgeChunk,
    KnowledgeDocument,
    ProcessingLog,
    ProgramNewsCache,
    ReportCache,
    RosterMember,
    Settings,
)
from intellibox.utils.datetime_utils import utcnow
from tests.pg_conftest import PgSessionLocal, pg_engine

pytestmark = pytest.mark.pg


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def pg_setup():
    """Create all tables once, drop at end."""
    Base.metadata.create_all(bind=pg_engine)
    yield pg_engine
    Base.metadata.drop_all(bind=pg_engine)
    pg_engine.dispose()


@pytest.fixture(autouse=True)
def pg_clean(pg_setup):
    """Truncate all tables between tests."""
    from sqlalchemy import text
    with pg_engine.connect() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(text(f'TRUNCATE TABLE "{table.name}" CASCADE'))
        conn.commit()


def _session():
    return PgSessionLocal()


def _make_email(session, **overrides):
    """Create and return an Email with sensible defaults."""
    defaults = dict(
        message_id=f"test-{utcnow().timestamp()}@example.com",
        subject="Test Subject",
        from_address="sender@example.com",
        to_addresses=json.dumps(["recipient@example.com"]),
        received_date=utcnow(),
        created_at=utcnow(),
    )
    defaults.update(overrides)
    email = Email(**defaults)
    session.add(email)
    session.flush()
    return email


# ── Table Creation ────────────────────────────────────────────────────────────

class TestTableCreation:
    """All 10 ORM tables created successfully on PostgreSQL."""

    def test_all_tables_exist(self):
        from sqlalchemy import inspect
        inspector = inspect(pg_engine)
        table_names = set(inspector.get_table_names())
        expected = {
            "emails", "actions", "assignments", "processing_log",
            "program_news_cache", "settings", "roster", "report_cache",
            "knowledge_documents", "knowledge_chunks",
        }
        assert expected.issubset(table_names), f"Missing: {expected - table_names}"


# ── CRUD Operations ──────────────────────────────────────────────────────────

class TestCRUD:
    """Insert, query, update, delete for every model."""

    def test_email_crud(self):
        session = _session()
        email = _make_email(session)
        session.commit()
        eid = email.id

        fetched = session.query(Email).get(eid)
        assert fetched.subject == "Test Subject"

        fetched.subject = "Updated Subject"
        session.commit()
        assert session.query(Email).get(eid).subject == "Updated Subject"

        session.delete(fetched)
        session.commit()
        assert session.query(Email).get(eid) is None
        session.close()

    def test_action_crud(self):
        session = _session()
        email = _make_email(session)
        action = Action(
            email_id=email.id, title="Do the thing", priority="high",
            created_at=utcnow(),
        )
        session.add(action)
        session.commit()
        assert action.id is not None

        fetched = session.query(Action).get(action.id)
        assert fetched.title == "Do the thing"
        assert fetched.priority == "high"
        session.close()

    def test_assignment_crud(self):
        session = _session()
        email = _make_email(session)
        action = Action(email_id=email.id, title="Task", created_at=utcnow())
        session.add(action)
        session.flush()
        assignment = Assignment(
            action_id=action.id, assigned_to="Alice", status="assigned",
            assigned_at=utcnow(),
        )
        session.add(assignment)
        session.commit()
        assert assignment.id is not None
        session.close()

    def test_settings_crud(self):
        session = _session()
        setting = Settings(key="test_key", value="test_value", updated_at=utcnow())
        session.add(setting)
        session.commit()

        fetched = session.query(Settings).filter_by(key="test_key").first()
        assert fetched.value == "test_value"
        session.close()

    def test_roster_crud(self):
        session = _session()
        member = RosterMember(
            first_name="John", last_name="Doe", email="john@example.com",
            created_at=utcnow(),
        )
        session.add(member)
        session.commit()
        assert member.id is not None
        assert member.active is True
        session.close()

    def test_knowledge_document_crud(self):
        session = _session()
        doc = KnowledgeDocument(
            filename="test.txt", file_type="txt", file_size=1024,
            extracted_text="Some text content", uploaded_at=utcnow(),
        )
        session.add(doc)
        session.commit()
        assert doc.id is not None
        session.close()

    def test_knowledge_chunk_crud(self):
        session = _session()
        doc = KnowledgeDocument(
            filename="test.txt", file_type="txt", file_size=100,
            uploaded_at=utcnow(),
        )
        session.add(doc)
        session.flush()
        chunk = KnowledgeChunk(
            document_id=doc.id, chunk_index=0, chunk_text="chunk content",
            embedding=json.dumps([0.1] * 10),
        )
        session.add(chunk)
        session.commit()
        assert chunk.id is not None
        session.close()

    def test_processing_log_crud(self):
        session = _session()
        log = ProcessingLog(
            event_type="test_event", status="success",
            message="All good", created_at=utcnow(),
        )
        session.add(log)
        session.commit()
        assert log.id is not None
        session.close()

    def test_program_news_cache_crud(self):
        session = _session()
        cache = ProgramNewsCache(
            summary="Weekly summary", days_covered=7,
            email_count=42, generated_at=utcnow(),
        )
        session.add(cache)
        session.commit()
        assert cache.id is not None
        session.close()

    def test_report_cache_crud(self):
        session = _session()
        cache = ReportCache(
            report_data=json.dumps({"key": "value"}),
            generated_at=utcnow(),
        )
        session.add(cache)
        session.commit()
        assert cache.id is not None
        session.close()


# ── Constraints ───────────────────────────────────────────────────────────────

class TestConstraints:
    """CHECK, UNIQUE, and FK constraints work on PostgreSQL."""

    def test_unique_message_id(self):
        session = _session()
        _make_email(session, message_id="unique@test.com")
        session.commit()
        _make_email(session, message_id="unique@test.com")
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        session.close()

    def test_unique_roster_email(self):
        session = _session()
        session.add(RosterMember(
            first_name="A", last_name="B", email="same@test.com",
            created_at=utcnow(),
        ))
        session.commit()
        session.add(RosterMember(
            first_name="C", last_name="D", email="same@test.com",
            created_at=utcnow(),
        ))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        session.close()

    def test_unique_settings_key(self):
        session = _session()
        session.add(Settings(key="dup_key", value="v1", updated_at=utcnow()))
        session.commit()
        session.add(Settings(key="dup_key", value="v2", updated_at=utcnow()))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        session.close()

    def test_check_priority_valid(self):
        session = _session()
        email = _make_email(session)
        for p in ("high", "medium", "low"):
            action = Action(email_id=email.id, title=f"P={p}", priority=p, created_at=utcnow())
            session.add(action)
        session.commit()
        session.close()

    def test_check_priority_invalid(self):
        session = _session()
        email = _make_email(session)
        action = Action(email_id=email.id, title="Bad", priority="urgent", created_at=utcnow())
        session.add(action)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        session.close()

    def test_check_status_valid(self):
        session = _session()
        email = _make_email(session)
        action = Action(email_id=email.id, title="T", created_at=utcnow())
        session.add(action)
        session.flush()
        for s in ("assigned", "completed"):
            a = Assignment(action_id=action.id, status=s, assigned_at=utcnow())
            session.add(a)
        session.commit()
        session.close()

    def test_check_status_invalid(self):
        session = _session()
        email = _make_email(session)
        action = Action(email_id=email.id, title="T", created_at=utcnow())
        session.add(action)
        session.flush()
        a = Assignment(action_id=action.id, status="invalid_status", assigned_at=utcnow())
        session.add(a)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        session.close()

    def test_fk_action_requires_valid_email(self):
        session = _session()
        action = Action(email_id=99999, title="Orphan", created_at=utcnow())
        session.add(action)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        session.close()


# ── CASCADE Deletes ───────────────────────────────────────────────────────────

class TestCascade:
    """Foreign key CASCADE behavior matches SQLite."""

    def test_delete_email_cascades_to_actions(self):
        session = _session()
        email = _make_email(session)
        action = Action(email_id=email.id, title="Cascaded", created_at=utcnow())
        session.add(action)
        session.commit()
        action_id = action.id

        session.delete(email)
        session.commit()
        assert session.query(Action).get(action_id) is None
        session.close()

    def test_delete_email_cascades_to_assignments(self):
        session = _session()
        email = _make_email(session)
        action = Action(email_id=email.id, title="T", created_at=utcnow())
        session.add(action)
        session.flush()
        assignment = Assignment(action_id=action.id, status="assigned", assigned_at=utcnow())
        session.add(assignment)
        session.commit()
        aid = assignment.id

        session.delete(email)
        session.commit()
        assert session.query(Assignment).get(aid) is None
        session.close()

    def test_delete_email_cascades_to_processing_log(self):
        session = _session()
        email = _make_email(session)
        log = ProcessingLog(
            email_id=email.id, event_type="test", status="success",
            created_at=utcnow(),
        )
        session.add(log)
        session.commit()
        lid = log.id

        session.delete(email)
        session.commit()
        assert session.query(ProcessingLog).get(lid) is None
        session.close()

    def test_delete_knowledge_doc_cascades_to_chunks(self):
        session = _session()
        doc = KnowledgeDocument(
            filename="f.txt", file_type="txt", file_size=10, uploaded_at=utcnow(),
        )
        session.add(doc)
        session.flush()
        chunk = KnowledgeChunk(document_id=doc.id, chunk_index=0, chunk_text="text")
        session.add(chunk)
        session.commit()
        cid = chunk.id

        session.delete(doc)
        session.commit()
        assert session.query(KnowledgeChunk).get(cid) is None
        session.close()


# ── JSON as TEXT Round-Trip ───────────────────────────────────────────────────

class TestJSONRoundTrip:
    """JSON stored in TEXT columns survives store/retrieve cycle."""

    def test_to_addresses_json(self):
        session = _session()
        original = json.dumps(["alice@example.com", "bob@example.com"])
        email = _make_email(session, to_addresses=original)
        session.commit()
        fetched = session.query(Email).get(email.id)
        assert fetched.to_addresses == original
        assert json.loads(fetched.to_addresses) == ["alice@example.com", "bob@example.com"]
        session.close()

    def test_also_received_from_json(self):
        session = _session()
        data = [{"address": "a@b.com", "name": "A B"}]
        email = _make_email(session, also_received_from=json.dumps(data))
        session.commit()
        fetched = session.query(Email).get(email.id)
        assert json.loads(fetched.also_received_from) == data
        session.close()

    def test_settings_json_value(self):
        session = _session()
        for val in [["a", "b"], {"key": "value"}, 42, "simple"]:
            key = f"test_{type(val).__name__}"
            session.add(Settings(key=key, value=json.dumps(val), updated_at=utcnow()))
        session.commit()

        for key, expected in [("test_list", ["a", "b"]), ("test_dict", {"key": "value"}),
                               ("test_int", 42), ("test_str", "simple")]:
            s = session.query(Settings).filter_by(key=key).first()
            assert json.loads(s.value) == expected
        session.close()

    def test_embedding_float_array(self):
        session = _session()
        doc = KnowledgeDocument(
            filename="f.txt", file_type="txt", file_size=10, uploaded_at=utcnow(),
        )
        session.add(doc)
        session.flush()
        floats = [0.123456789] * 100
        chunk = KnowledgeChunk(
            document_id=doc.id, chunk_index=0, chunk_text="text",
            embedding=json.dumps(floats),
        )
        session.add(chunk)
        session.commit()
        fetched = session.query(KnowledgeChunk).get(chunk.id)
        assert json.loads(fetched.embedding) == floats
        session.close()


# ── Datetime Handling ─────────────────────────────────────────────────────────

class TestDatetime:
    """Naive datetimes stored/retrieved without timezone mangling."""

    def test_naive_datetime_roundtrip(self):
        from datetime import datetime
        session = _session()
        dt = datetime(2026, 2, 19, 14, 30, 45, 123456)
        email = _make_email(session, received_date=dt, created_at=dt)
        session.commit()
        fetched = session.query(Email).get(email.id)
        assert fetched.received_date == dt
        assert fetched.created_at == dt
        assert fetched.received_date.tzinfo is None
        session.close()

    def test_datetime_ordering(self):
        from datetime import datetime, timedelta
        session = _session()
        base = datetime(2026, 1, 1)
        for i in [5, 2, 8, 1, 9]:
            _make_email(
                session,
                message_id=f"order-{i}@test.com",
                received_date=base + timedelta(days=i),
            )
        session.commit()
        emails = session.query(Email).order_by(Email.received_date.desc()).all()
        dates = [e.received_date for e in emails]
        assert dates == sorted(dates, reverse=True)
        session.close()
