"""Shared pytest configuration and fixtures for all tests."""

import os
import tempfile
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from intellibox.models import Base

# Create ONE shared test database for all test modules
test_db_fd, test_db_path = tempfile.mkstemp(suffix='_shared.db', prefix='test_intellibox_')
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


# Patch get_session at the database module level — deps.get_session() delegates there
import intellibox.database as database_module
import intellibox.settings_service as settings_service_module

database_module.get_session = override_get_session
settings_service_module.get_session = override_get_session


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Create tables once for entire test session."""
    Base.metadata.create_all(bind=test_engine)
    yield
    # Clean up at end of all tests
    test_engine.dispose()
    try:
        os.close(test_db_fd)
        os.unlink(test_db_path)
    except:
        pass
