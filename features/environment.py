"""
Behave environment hooks for INtelliBOX BDD test suite.

Supports two modes controlled by the TEST_BASE_URL environment variable:

1. In-process (default): Uses FastAPI TestClient with a temp SQLite DB.
   Same as the original implementation — patches get_session in all 3 modules.

2. Container mode (TEST_BASE_URL=http://localhost:8001):
   Uses requests library for HTTP calls. All data operations go through the
   container's test API (/api/test/seed, /api/test/query/*).
"""

import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class RequestsClientAdapter:
    """Wraps requests.Session to match the TestClient API.

    TestClient (httpx) uses ``follow_redirects``; requests uses
    ``allow_redirects``.  Both expose ``.content`` (bytes),
    ``.status_code``, and ``.json()`` identically.
    """

    def __init__(self, base_url):
        import requests as _requests
        self._session = _requests.Session()
        self._base_url = base_url.rstrip("/")

    def get(self, path, **kwargs):
        return self._session.get(f"{self._base_url}{path}", **kwargs)

    def post(self, path, follow_redirects=True, **kwargs):
        kwargs["allow_redirects"] = follow_redirects
        return self._session.post(f"{self._base_url}{path}", **kwargs)


def before_all(context):
    """Create shared test database and patch get_session before any scenario runs."""
    base_url = os.environ.get("TEST_BASE_URL")

    if base_url:
        # ---- Container mode ----
        context._container_mode = True
        context._base_url = base_url
        context.client = RequestsClientAdapter(base_url)

    else:
        # ---- In-process mode (original behaviour) ----
        fd, db_path = tempfile.mkstemp(suffix="_behave.db", prefix="test_emailtools_")
        os.close(fd)
        context._db_path = db_path
        context._container_mode = False

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
    if getattr(context, "_container_mode", False):
        import requests as _requests
        resp = _requests.post(f"{context._base_url}/api/test/reset")
        assert resp.status_code == 200, f"Test reset failed: {resp.text}"
    else:
        from emailtools.models import Base
        Base.metadata.drop_all(context._engine)
        Base.metadata.create_all(context._engine)


def after_all(context):
    """Clean up the temporary database file."""
    if not getattr(context, "_container_mode", False):
        context._engine.dispose()
        try:
            os.unlink(context._db_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Helpers for step definitions — work in both modes
# ---------------------------------------------------------------------------

def make_session(context):
    """Return a raw SQLAlchemy session (in-process mode only)."""
    return context._Session()


def seed(context, entity_type, **kwargs):
    """Create a test entity and return its ID.

    - In-process: uses SQLAlchemy directly
    - Container: calls POST /api/test/seed
    """
    if getattr(context, "_container_mode", False):
        import requests as _requests
        data = {}
        for k, v in kwargs.items():
            if isinstance(v, datetime):
                data[k] = v.isoformat()
            else:
                data[k] = v
        resp = _requests.post(
            f"{context._base_url}/api/test/seed",
            json={"type": entity_type, "data": data},
        )
        assert resp.status_code == 200, f"Seed {entity_type} failed: {resp.text}"
        return resp.json()["id"]
    else:
        from emailtools.models import Email, Action, Assignment, RosterMember, KnowledgeDocument
        model_map = {
            "email": Email, "action": Action,
            "assignment": Assignment, "roster_member": RosterMember,
            "knowledge_document": KnowledgeDocument,
        }
        session = make_session(context)
        entity = model_map[entity_type](**kwargs)
        session.add(entity)
        session.commit()
        entity_id = entity.id
        session.close()
        return entity_id


def query_action(context, action_id):
    """Query an action by ID. Returns dict or None."""
    if getattr(context, "_container_mode", False):
        import requests as _requests
        resp = _requests.get(f"{context._base_url}/api/test/query/action/{action_id}")
        data = resp.json()
        return data if data.get("found") else None
    else:
        from emailtools.models import Action
        session = make_session(context)
        action = session.query(Action).filter_by(id=action_id).first()
        if not action:
            session.close()
            return None
        result = {
            "found": True,
            "id": action.id,
            "title": action.title,
            "priority": action.priority,
            "due_date": action.due_date.isoformat() if action.due_date else None,
            "category": action.category,
            "has_assignments": bool(action.assignments and len(action.assignments) > 0),
        }
        session.close()
        return result


def query_assignment(context, action_id):
    """Query an assignment by action_id. Returns dict or None."""
    if getattr(context, "_container_mode", False):
        import requests as _requests
        resp = _requests.get(
            f"{context._base_url}/api/test/query/assignment",
            params={"action_id": action_id},
        )
        data = resp.json()
        return data if data.get("found") else None
    else:
        from emailtools.models import Assignment
        session = make_session(context)
        assignment = session.query(Assignment).filter_by(action_id=action_id).first()
        if not assignment:
            session.close()
            return None
        result = {
            "found": True,
            "id": assignment.id,
            "action_id": assignment.action_id,
            "assigned_to": assignment.assigned_to,
            "status": assignment.status,
        }
        session.close()
        return result


def query_roster_count(context):
    """Count roster members. Returns int."""
    if getattr(context, "_container_mode", False):
        import requests as _requests
        resp = _requests.get(f"{context._base_url}/api/test/query/roster/count")
        return resp.json()["count"]
    else:
        from emailtools.models import RosterMember
        session = make_session(context)
        count = session.query(RosterMember).count()
        session.close()
        return count


def query_roster_member(context, member_id):
    """Query a roster member by ID. Returns dict or None."""
    if getattr(context, "_container_mode", False):
        import requests as _requests
        resp = _requests.get(f"{context._base_url}/api/test/query/roster-member/{member_id}")
        data = resp.json()
        return data if data.get("found") else None
    else:
        from emailtools.models import RosterMember
        session = make_session(context)
        member = session.query(RosterMember).filter_by(id=member_id).first()
        if not member:
            session.close()
            return None
        result = {"found": True, "id": member.id}
        session.close()
        return result
