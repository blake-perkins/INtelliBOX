"""Database initialization and session management."""

from contextlib import contextmanager
from datetime import timedelta
from typing import Dict, Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from intellibox.config import settings
from intellibox.models import Base
from intellibox.utils.datetime_utils import utcnow


def _build_engine():
    """Build SQLAlchemy engine with dialect-appropriate configuration."""
    url = settings.database_url
    kwargs = {
        "echo": settings.log_level == "DEBUG",
        "future": True,
    }

    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    elif url.startswith("postgresql"):
        kwargs["pool_size"] = settings.db_pool_size
        kwargs["max_overflow"] = settings.db_max_overflow
        kwargs["pool_recycle"] = settings.db_pool_recycle
        kwargs["pool_pre_ping"] = settings.db_pool_pre_ping

    return create_engine(url, **kwargs)


engine = _build_engine()


def configure_sqlite_pragmas(target_engine) -> None:
    """Register SQLite pragmas on new connections for the given engine."""

    @event.listens_for(target_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA cache_size=-64000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


# Enable pragmas for the default engine (SQLite only)
if settings.database_url.startswith("sqlite"):
    configure_sqlite_pragmas(engine)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    future=True,
)


def init_db() -> None:
    """Initialize the database by creating all tables."""
    Base.metadata.create_all(bind=engine)


def drop_db() -> None:
    """Drop all database tables. Use with caution!"""
    Base.metadata.drop_all(bind=engine)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Context manager for database sessions.

    Usage:
        with get_session() as session:
            email = session.query(Email).first()
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency for FastAPI (future use).

    Usage in FastAPI:
        @app.get("/emails")
        def get_emails(db: Session = Depends(get_db)):
            return db.query(Email).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Maintenance Functions ────────────────────────────────────────────────────

def cleanup_cache_tables(
    session: Session,
    keep_program_news: int = 5,
    keep_report: int = 5,
) -> Dict[str, int]:
    """Delete old cache rows, keeping only the N most recent of each.

    Args:
        session: Active database session (caller must commit).
        keep_program_news: Number of ProgramNewsCache rows to keep (0 = skip).
        keep_report: Number of ReportCache rows to keep (0 = skip).

    Returns:
        Dict with ``program_news_deleted`` and ``report_deleted`` counts.
    """
    from intellibox.models import ProgramNewsCache, ReportCache

    pn_deleted = 0
    if keep_program_news > 0:
        # IDs to keep: the N most recent
        keep_ids = [
            row.id for row in
            session.query(ProgramNewsCache.id)
            .order_by(ProgramNewsCache.generated_at.desc())
            .limit(keep_program_news)
            .all()
        ]
        if keep_ids:
            pn_deleted = (
                session.query(ProgramNewsCache)
                .filter(ProgramNewsCache.id.notin_(keep_ids))
                .delete(synchronize_session="fetch")
            )

    rpt_deleted = 0
    if keep_report > 0:
        keep_ids = [
            row.id for row in
            session.query(ReportCache.id)
            .order_by(ReportCache.generated_at.desc())
            .limit(keep_report)
            .all()
        ]
        if keep_ids:
            rpt_deleted = (
                session.query(ReportCache)
                .filter(ReportCache.id.notin_(keep_ids))
                .delete(synchronize_session="fetch")
            )

    return {"program_news_deleted": pn_deleted, "report_deleted": rpt_deleted}


def cleanup_processing_logs(session: Session, retention_days: int = 90) -> int:
    """Delete ProcessingLog entries older than *retention_days*.

    Returns:
        Number of rows deleted.
    """
    from intellibox.models import ProcessingLog

    cutoff = utcnow() - timedelta(days=retention_days)
    deleted = (
        session.query(ProcessingLog)
        .filter(ProcessingLog.created_at < cutoff)
        .delete(synchronize_session="fetch")
    )
    return deleted


def _is_sqlite_engine(eng) -> bool:
    """Check if the given engine is backed by SQLite."""
    return str(eng.url).startswith("sqlite")


def run_vacuum(target_engine=None) -> None:
    """Run VACUUM to reclaim disk space.

    Uses SQLAlchemy's AUTOCOMMIT isolation level so VACUUM runs outside
    a transaction block (required by both SQLite and PostgreSQL).
    """
    eng = target_engine or engine
    with eng.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        if _is_sqlite_engine(eng):
            conn.execute(text("VACUUM"))
        else:
            conn.execute(text("VACUUM ANALYZE"))


def run_analyze(target_engine=None) -> None:
    """Run ANALYZE to update query planner statistics."""
    eng = target_engine or engine
    with eng.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("ANALYZE"))


def run_maintenance(session: Session, target_engine=None) -> Dict:
    """Run all maintenance tasks and return a summary.

    1. Clean cache tables (keep 5 most recent of each)
    2. Clean old processing logs (retain 90 days)
    3. Run ANALYZE
    4. Run VACUUM (last — locks DB briefly on SQLite)
    """
    eng = target_engine or engine

    cache_result = cleanup_cache_tables(session)
    logs_deleted = cleanup_processing_logs(session)
    session.commit()

    analyze_status = "ok"
    try:
        run_analyze(eng)
    except Exception as e:
        analyze_status = str(e)

    vacuum_status = "ok"
    try:
        run_vacuum(eng)
    except Exception as e:
        vacuum_status = str(e)

    return {
        **cache_result,
        "logs_deleted": logs_deleted,
        "analyze": analyze_status,
        "vacuum": vacuum_status,
    }
