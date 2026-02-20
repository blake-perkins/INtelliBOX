"""Stress test fixtures — uses the dedicated postgres-stress instance (port 5434)."""

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from intellibox.models import Base

PG_STRESS_URL = os.environ.get(
    "PG_STRESS_DATABASE_URL",
    "postgresql+psycopg://intellibox_stress:stress_password@localhost:5434/intellibox_stress",
)

stress_engine = create_engine(PG_STRESS_URL, pool_size=50, max_overflow=100, pool_pre_ping=True)
StressSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=stress_engine)


@pytest.fixture(scope="session")
def stress_setup():
    """Create all tables once on the stress database."""
    Base.metadata.create_all(bind=stress_engine)
    yield stress_engine
    Base.metadata.drop_all(bind=stress_engine)
    stress_engine.dispose()


@pytest.fixture(autouse=True)
def stress_clean(stress_setup):
    """Truncate between tests."""
    with stress_engine.connect() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(text(f'TRUNCATE TABLE "{table.name}" CASCADE'))
        conn.commit()
