"""Shared PostgreSQL test infrastructure — engine, session factory, and fixtures.

Requires a running PostgreSQL instance (see docker-compose.pg-test.yml).
Default connection: localhost:5433/intellibox_test

Usage:
    docker compose -f docker-compose.pg-test.yml up -d
    python -m pytest tests/test_pg_functional.py -v
"""

import os
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from intellibox.models import Base

PG_TEST_URL = os.environ.get(
    "PG_TEST_DATABASE_URL",
    "postgresql+psycopg://intellibox_test:test_password@localhost:5433/intellibox_test",
)

pg_engine = create_engine(
    PG_TEST_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=300,
)
PgSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=pg_engine)


@contextmanager
def pg_override_get_session():
    """Override get_session for PostgreSQL tests."""
    session = PgSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@pytest.fixture(scope="session")
def pg_setup():
    """Create all tables once for the test session, drop at end."""
    Base.metadata.create_all(bind=pg_engine)
    yield pg_engine
    Base.metadata.drop_all(bind=pg_engine)
    pg_engine.dispose()


@pytest.fixture(autouse=True)
def pg_clean_tables(pg_setup):
    """Truncate all tables between tests for isolation (faster than drop/recreate)."""
    with pg_engine.connect() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(text(f'TRUNCATE TABLE "{table.name}" CASCADE'))
        conn.commit()
    yield
