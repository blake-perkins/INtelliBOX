"""
Behave environment hooks for INtelliBOX BDD test suite.

Uses the same database-patching pattern as the pytest conftest.py:
- Temp SQLite database per test run
- get_session patched in all 3 locations
- FastAPI TestClient for HTTP-level testing
- Clean tables before every scenario
"""

import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def before_all(context):
    """Create shared test database and patch get_session before any scenario runs."""
    fd, db_path = tempfile.mkstemp(suffix="_behave.db", prefix="test_emailtools_")
    os.close(fd)
    context._db_path = db_path

    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    @contextmanager
    def override_get_session():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    context._engine = engine
    context._Session = Session
    context._override_get_session = override_get_session

    # Patch all three locations where get_session is used (same as conftest.py)
    import emailtools.database as database_module
    import emailtools.settings_service as settings_service_module
    import emailtools.web.app as app_module

    database_module.get_session = override_get_session
    settings_service_module.get_session = override_get_session
    app_module.get_session = override_get_session

    from emailtools.models import Base
    Base.metadata.create_all(engine)

    from fastapi.testclient import TestClient
    from emailtools.web.app import app
    context.client = TestClient(app)


def before_scenario(context, scenario):
    """Drop and recreate all tables before each scenario for a clean slate."""
    from emailtools.models import Base
    Base.metadata.drop_all(context._engine)
    Base.metadata.create_all(context._engine)


def after_all(context):
    """Clean up the temporary database file."""
    context._engine.dispose()
    try:
        os.unlink(context._db_path)
    except OSError:
        pass


def make_session(context):
    """Helper: return a raw session for use in step definitions."""
    return context._Session()
