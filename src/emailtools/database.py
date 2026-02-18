"""Database initialization and session management."""

from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from emailtools.config import settings
from emailtools.models import Base


# Build connect_args for SQLite compatibility
_connect_args = {}
if settings.database_url.startswith("sqlite"):
    _connect_args["check_same_thread"] = False

# Create database engine
engine = create_engine(
    settings.database_url,
    echo=settings.log_level == "DEBUG",  # Log SQL queries in debug mode
    future=True,
    connect_args=_connect_args,
)

# Enable WAL journal mode for SQLite (better concurrent read/write)
if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

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
