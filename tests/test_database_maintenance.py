"""Tests for database maintenance functions (cleanup, vacuum, pragmas)."""

import tempfile
import os
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager

from emailtools.models import Base, ProgramNewsCache, ReportCache, ProcessingLog, Email


# Create a unique temp database for this module
test_db_fd, test_db_path = tempfile.mkstemp(suffix='_db_maintenance.db', prefix='test_emailtools_')
TEST_DATABASE_URL = f"sqlite:///{test_db_path}"
test_engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@contextmanager
def override_get_session():
    """Override database session for testing."""
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


# Patch before importing maintenance functions
import emailtools.database as database_module
database_module.get_session = override_get_session

from emailtools.database import (
    cleanup_cache_tables,
    cleanup_processing_logs,
    run_vacuum,
    run_analyze,
    run_maintenance,
)


@pytest.fixture(scope="module", autouse=True)
def setup_test_database():
    """Create tables once for all tests in this module."""
    Base.metadata.create_all(bind=test_engine)
    yield
    test_engine.dispose()
    os.close(test_db_fd)
    try:
        os.unlink(test_db_path)
    except Exception:
        pass


@pytest.fixture(scope="function")
def db_session():
    """Provide a clean session for each test."""
    # Clear relevant tables
    with override_get_session() as session:
        session.query(ProgramNewsCache).delete()
        session.query(ReportCache).delete()
        session.query(ProcessingLog).delete()
        session.commit()
    test_engine.dispose()

    session = TestSessionLocal()
    yield session
    session.close()

    # Cleanup
    with override_get_session() as session:
        session.query(ProgramNewsCache).delete()
        session.query(ReportCache).delete()
        session.query(ProcessingLog).delete()
        session.commit()
    test_engine.dispose()


# ── SQLite Pragma Tests ─────────────────────────────────────────────────────

class TestSQLitePragmas:
    """Test SQLite pragma configuration."""

    def test_busy_timeout_set(self):
        """busy_timeout pragma should be set on new connections."""
        from emailtools.database import configure_sqlite_pragmas

        temp_fd, temp_path = tempfile.mkstemp(suffix='_pragma_test.db')
        temp_engine = create_engine(f"sqlite:///{temp_path}")
        configure_sqlite_pragmas(temp_engine)

        with temp_engine.connect() as conn:
            result = conn.execute(text("PRAGMA busy_timeout")).fetchone()
            assert result[0] == 5000

        temp_engine.dispose()
        os.close(temp_fd)
        os.unlink(temp_path)

    def test_cache_size_set(self):
        """cache_size pragma should be set on new connections."""
        from emailtools.database import configure_sqlite_pragmas

        temp_fd, temp_path = tempfile.mkstemp(suffix='_pragma_test.db')
        temp_engine = create_engine(f"sqlite:///{temp_path}")
        configure_sqlite_pragmas(temp_engine)

        with temp_engine.connect() as conn:
            result = conn.execute(text("PRAGMA cache_size")).fetchone()
            assert result[0] == -64000

        temp_engine.dispose()
        os.close(temp_fd)
        os.unlink(temp_path)

    def test_wal_mode_set(self):
        """journal_mode should be WAL."""
        from emailtools.database import configure_sqlite_pragmas

        temp_fd, temp_path = tempfile.mkstemp(suffix='_pragma_test.db')
        temp_engine = create_engine(f"sqlite:///{temp_path}")
        configure_sqlite_pragmas(temp_engine)

        with temp_engine.connect() as conn:
            result = conn.execute(text("PRAGMA journal_mode")).fetchone()
            assert result[0].lower() == "wal"

        temp_engine.dispose()
        os.close(temp_fd)
        os.unlink(temp_path)


# ── Cache Cleanup Tests ─────────────────────────────────────────────────────

class TestCacheCleanup:
    """Test cache table cleanup functions."""

    def test_cleanup_program_news_keeps_latest(self, db_session):
        """Cleanup keeps only the N most recent ProgramNewsCache rows."""
        now = datetime.utcnow()
        for i in range(5):
            db_session.add(ProgramNewsCache(
                summary=f"summary_{i}",
                days_covered=7,
                email_count=10,
                generated_at=now - timedelta(hours=i),
            ))
        db_session.commit()

        result = cleanup_cache_tables(db_session, keep_program_news=2, keep_report=5)
        db_session.commit()

        remaining = db_session.query(ProgramNewsCache).order_by(
            ProgramNewsCache.generated_at.desc()
        ).all()
        assert len(remaining) == 2
        assert remaining[0].summary == "summary_0"  # newest
        assert remaining[1].summary == "summary_1"
        assert result["program_news_deleted"] == 3

    def test_cleanup_program_news_empty_table(self, db_session):
        """Cleanup on empty ProgramNewsCache does not error."""
        result = cleanup_cache_tables(db_session, keep_program_news=2, keep_report=5)
        assert result["program_news_deleted"] == 0

    def test_cleanup_program_news_fewer_than_keep(self, db_session):
        """If fewer rows exist than keep count, nothing is deleted."""
        now = datetime.utcnow()
        db_session.add(ProgramNewsCache(
            summary="only_one", days_covered=7, email_count=1,
            generated_at=now,
        ))
        db_session.commit()

        result = cleanup_cache_tables(db_session, keep_program_news=5, keep_report=5)
        assert result["program_news_deleted"] == 0
        assert db_session.query(ProgramNewsCache).count() == 1

    def test_cleanup_report_cache_keeps_latest(self, db_session):
        """Cleanup keeps only the N most recent ReportCache rows."""
        now = datetime.utcnow()
        for i in range(5):
            db_session.add(ReportCache(
                report_data=f'{{"data": {i}}}',
                generated_at=now - timedelta(hours=i),
            ))
        db_session.commit()

        result = cleanup_cache_tables(db_session, keep_program_news=5, keep_report=2)
        db_session.commit()

        remaining = db_session.query(ReportCache).count()
        assert remaining == 2
        assert result["report_deleted"] == 3

    def test_cleanup_report_cache_empty_table(self, db_session):
        """Cleanup on empty ReportCache does not error."""
        result = cleanup_cache_tables(db_session, keep_program_news=5, keep_report=2)
        assert result["report_deleted"] == 0

    def test_cleanup_zero_keep_deletes_all(self, db_session):
        """keep=0 for a cache skips cleanup for that table (does NOT delete all)."""
        now = datetime.utcnow()
        db_session.add(ProgramNewsCache(
            summary="keep me", days_covered=7, email_count=1,
            generated_at=now,
        ))
        db_session.commit()

        result = cleanup_cache_tables(db_session, keep_program_news=0, keep_report=5)
        # keep=0 means "skip this table"
        assert db_session.query(ProgramNewsCache).count() == 1
        assert result["program_news_deleted"] == 0


# ── ProcessingLog Retention Tests ────────────────────────────────────────────

class TestProcessingLogRetention:
    """Test ProcessingLog cleanup by age."""

    def test_cleanup_logs_by_age(self, db_session):
        """Logs older than retention_days are deleted."""
        now = datetime.utcnow()
        # Recent log (10 days ago)
        db_session.add(ProcessingLog(
            event_type="email_received", status="success",
            message="recent", created_at=now - timedelta(days=10),
        ))
        # Old log (100 days ago)
        db_session.add(ProcessingLog(
            event_type="email_received", status="success",
            message="old", created_at=now - timedelta(days=100),
        ))
        db_session.commit()

        deleted = cleanup_processing_logs(db_session, retention_days=90)
        db_session.commit()

        assert deleted == 1
        remaining = db_session.query(ProcessingLog).all()
        assert len(remaining) == 1
        assert remaining[0].message == "recent"

    def test_cleanup_logs_preserves_recent(self, db_session):
        """All recent logs are preserved."""
        now = datetime.utcnow()
        for i in range(5):
            db_session.add(ProcessingLog(
                event_type="test", status="success",
                created_at=now - timedelta(days=i),
            ))
        db_session.commit()

        deleted = cleanup_processing_logs(db_session, retention_days=90)
        assert deleted == 0
        assert db_session.query(ProcessingLog).count() == 5

    def test_cleanup_logs_empty_table(self, db_session):
        """Cleanup on empty ProcessingLog does not error."""
        deleted = cleanup_processing_logs(db_session, retention_days=90)
        assert deleted == 0

    def test_cleanup_logs_boundary(self, db_session):
        """Log just inside retention boundary is preserved."""
        now = datetime.utcnow()
        # 89 days ago — safely within retention, must be kept
        db_session.add(ProcessingLog(
            event_type="boundary", status="success",
            created_at=now - timedelta(days=89),
        ))
        # 91 days ago — clearly outside retention, must be deleted
        db_session.add(ProcessingLog(
            event_type="just_over", status="success",
            created_at=now - timedelta(days=91),
        ))
        db_session.commit()

        deleted = cleanup_processing_logs(db_session, retention_days=90)
        db_session.commit()

        assert deleted == 1
        remaining = db_session.query(ProcessingLog).all()
        assert len(remaining) == 1
        assert remaining[0].event_type == "boundary"


# ── VACUUM / ANALYZE Tests ──────────────────────────────────────────────────

class TestVacuumAnalyze:
    """Test VACUUM and ANALYZE operations."""

    def test_run_vacuum(self, db_session):
        """VACUUM completes without error and DB remains accessible."""
        # Insert and delete some data to create space to reclaim
        db_session.add(ProgramNewsCache(
            summary="temp", days_covered=7, email_count=1,
            generated_at=datetime.utcnow(),
        ))
        db_session.commit()
        db_session.query(ProgramNewsCache).delete()
        db_session.commit()

        run_vacuum(test_engine)

        # Verify DB is still accessible
        count = db_session.query(ProgramNewsCache).count()
        assert count == 0

    def test_run_analyze(self, db_session):
        """ANALYZE completes without error."""
        run_analyze(test_engine)

        # Verify DB is still accessible
        count = db_session.query(ProgramNewsCache).count()
        assert count == 0


# ── Combined Maintenance Test ────────────────────────────────────────────────

class TestRunMaintenance:
    """Test the combined maintenance runner."""

    def test_run_maintenance_cleans_all(self, db_session):
        """run_maintenance cleans caches, logs, and runs vacuum/analyze."""
        now = datetime.utcnow()

        # Add old cache entries
        for i in range(10):
            db_session.add(ProgramNewsCache(
                summary=f"news_{i}", days_covered=7, email_count=1,
                generated_at=now - timedelta(hours=i),
            ))
        for i in range(10):
            db_session.add(ReportCache(
                report_data=f'{{"data": {i}}}',
                generated_at=now - timedelta(hours=i),
            ))

        # Add old processing logs
        db_session.add(ProcessingLog(
            event_type="old_event", status="success",
            created_at=now - timedelta(days=120),
        ))
        db_session.add(ProcessingLog(
            event_type="recent_event", status="success",
            created_at=now - timedelta(days=5),
        ))
        db_session.commit()

        result = run_maintenance(db_session, test_engine)

        assert result["program_news_deleted"] > 0
        assert result["report_deleted"] > 0
        assert result["logs_deleted"] == 1
        assert result["vacuum"] == "ok"
        assert result["analyze"] == "ok"

        # Verify only recent data remains
        assert db_session.query(ProgramNewsCache).count() == 5
        assert db_session.query(ReportCache).count() == 5
        assert db_session.query(ProcessingLog).count() == 1
