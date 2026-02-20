"""
Tests for authentication and authorization (AUTH_MODE=local).

Covers: password hashing, login/logout flow, session management,
middleware redirects, role enforcement, and session cleanup.
"""

import os
import tempfile
from contextlib import contextmanager
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Force AUTH_MODE=local before any app imports
os.environ["AUTH_MODE"] = "local"

from intellibox.database import Base
from intellibox.models import User, UserSession
from intellibox.utils.datetime_utils import utcnow
from intellibox.web.auth import (
    SESSION_COOKIE,
    create_session,
    destroy_session,
    hash_password,
    resolve_user_from_session,
    verify_password,
)

# ── Test database setup ─────────────────────────────────────────────────────

test_db_fd, test_db_path = tempfile.mkstemp(suffix="_auth.db", prefix="test_intellibox_")
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


# Patch get_session before importing app
import intellibox.database as database_module
import intellibox.settings_service as settings_service_module

database_module.get_session = override_get_session
settings_service_module.get_session = override_get_session

from intellibox.web.app import app

client = TestClient(app, follow_redirects=False)


@pytest.fixture(autouse=True)
def setup_database():
    """Create tables and seed an admin + member user before each test."""
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    session = TestSessionLocal()
    try:
        admin = User(
            username="admin",
            email="admin@example.com",
            display_name="Admin User",
            password_hash=hash_password("adminpass"),
            role="admin",
            is_active=True,
        )
        member = User(
            username="member",
            email="member@example.com",
            display_name="Member User",
            password_hash=hash_password("memberpass"),
            role="member",
            is_active=True,
        )
        inactive = User(
            username="inactive",
            email="inactive@example.com",
            display_name="Inactive User",
            password_hash=hash_password("inactivepass"),
            role="member",
            is_active=False,
        )
        session.add_all([admin, member, inactive])
        session.commit()
    finally:
        session.close()

    yield

    Base.metadata.drop_all(bind=test_engine)


# ── Password hashing tests ──────────────────────────────────────────────────


class TestPasswordHashing:
    def test_hash_and_verify(self):
        hashed = hash_password("secret123")
        assert hashed != "secret123"
        assert verify_password("secret123", hashed)

    def test_wrong_password_fails(self):
        hashed = hash_password("correct")
        assert not verify_password("wrong", hashed)

    def test_different_hashes_for_same_password(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # bcrypt salts differ
        assert verify_password("same", h1)
        assert verify_password("same", h2)


# ── Session management tests ────────────────────────────────────────────────


class TestSessionManagement:
    def test_create_and_resolve_session(self):
        with override_get_session() as session:
            user = session.query(User).filter_by(username="admin").first()
            session_id = create_session(user.id, session)

            assert session_id is not None
            resolved = resolve_user_from_session(session_id, session)
            assert resolved is not None
            assert resolved.username == "admin"

    def test_resolve_empty_session_id(self):
        with override_get_session() as session:
            assert resolve_user_from_session("", session) is None
            assert resolve_user_from_session(None, session) is None

    def test_resolve_nonexistent_session(self):
        with override_get_session() as session:
            assert resolve_user_from_session("no-such-session-id", session) is None

    def test_expired_session_not_resolved(self):
        with override_get_session() as session:
            user = session.query(User).filter_by(username="admin").first()
            session_id = create_session(user.id, session)

            # Manually expire the session
            user_session = session.query(UserSession).filter_by(id=session_id).first()
            user_session.expires_at = utcnow() - timedelta(hours=1)
            session.commit()

            assert resolve_user_from_session(session_id, session) is None

    def test_destroy_session(self):
        with override_get_session() as session:
            user = session.query(User).filter_by(username="admin").first()
            session_id = create_session(user.id, session)

            destroy_session(session_id, session)
            assert resolve_user_from_session(session_id, session) is None

    def test_inactive_user_session_not_resolved(self):
        with override_get_session() as session:
            user = session.query(User).filter_by(username="inactive").first()
            session_id = create_session(user.id, session)
            assert resolve_user_from_session(session_id, session) is None


# ── Login flow tests ────────────────────────────────────────────────────────


class TestLoginFlow:
    def test_login_page_renders(self):
        response = client.get("/auth/login")
        assert response.status_code == 200
        assert b"Sign in to INtelliBOX" in response.content

    def test_successful_login_redirects(self):
        response = client.post(
            "/auth/login",
            data={"username": "admin", "password": "adminpass", "next": "/"},
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/"
        assert SESSION_COOKIE in response.cookies

    def test_login_sets_session_cookie(self):
        response = client.post(
            "/auth/login",
            data={"username": "admin", "password": "adminpass", "next": "/"},
        )
        cookie = response.cookies.get(SESSION_COOKIE)
        assert cookie is not None
        # Session ID should be a valid UUID-like string
        assert len(cookie) == 36

    def test_invalid_password_redirects_with_error(self):
        response = client.post(
            "/auth/login",
            data={"username": "admin", "password": "wrong", "next": "/"},
        )
        assert response.status_code == 303
        assert "error=Invalid" in response.headers["location"]
        assert SESSION_COOKIE not in response.cookies

    def test_nonexistent_user_redirects_with_error(self):
        response = client.post(
            "/auth/login",
            data={"username": "nobody", "password": "x", "next": "/"},
        )
        assert response.status_code == 303
        assert "error=Invalid" in response.headers["location"]

    def test_inactive_user_cannot_login(self):
        response = client.post(
            "/auth/login",
            data={"username": "inactive", "password": "inactivepass", "next": "/"},
        )
        assert response.status_code == 303
        assert "error=Invalid" in response.headers["location"]

    def test_login_updates_last_login(self):
        before = utcnow()
        client.post(
            "/auth/login",
            data={"username": "admin", "password": "adminpass", "next": "/"},
        )
        with override_get_session() as session:
            user = session.query(User).filter_by(username="admin").first()
            assert user.last_login is not None
            assert user.last_login >= before

    def test_login_next_param_preserved(self):
        response = client.post(
            "/auth/login",
            data={"username": "admin", "password": "adminpass", "next": "/actions"},
        )
        assert response.headers["location"] == "/actions"

    def test_login_next_param_sanitized(self):
        """Non-relative next values are replaced with /."""
        response = client.post(
            "/auth/login",
            data={"username": "admin", "password": "adminpass", "next": "https://evil.com"},
        )
        assert response.headers["location"] == "/"


# ── Logout flow tests ───────────────────────────────────────────────────────


class TestLogoutFlow:
    def test_logout_redirects_to_login(self):
        # Login first
        login_resp = client.post(
            "/auth/login",
            data={"username": "admin", "password": "adminpass", "next": "/"},
        )
        session_cookie = login_resp.cookies.get(SESSION_COOKIE)

        # Logout
        response = client.get("/auth/logout", cookies={SESSION_COOKIE: session_cookie})
        assert response.status_code == 303
        assert response.headers["location"] == "/auth/login"

    def test_logout_destroys_server_session(self):
        # Login
        login_resp = client.post(
            "/auth/login",
            data={"username": "admin", "password": "adminpass", "next": "/"},
        )
        session_cookie = login_resp.cookies.get(SESSION_COOKIE)

        # Logout
        client.get("/auth/logout", cookies={SESSION_COOKIE: session_cookie})

        # Session should be gone from DB
        with override_get_session() as session:
            row = session.query(UserSession).filter_by(id=session_cookie).first()
            assert row is None

    def test_logout_without_session_still_redirects(self):
        response = client.get("/auth/logout")
        assert response.status_code == 303
        assert response.headers["location"] == "/auth/login"


# ── Middleware redirect tests ────────────────────────────────────────────────


class TestAuthMiddleware:
    def test_unauthenticated_redirected_to_login(self):
        response = client.get("/")
        assert response.status_code == 302
        assert "/auth/login" in response.headers["location"]

    def test_unauthenticated_redirect_preserves_next(self):
        response = client.get("/actions")
        assert response.status_code == 302
        assert "next=/actions" in response.headers["location"]

    def test_public_paths_not_redirected(self):
        assert client.get("/auth/login").status_code == 200
        assert client.get("/health").status_code == 200

    def test_authenticated_user_can_access_routes(self):
        # Login
        login_resp = client.post(
            "/auth/login",
            data={"username": "admin", "password": "adminpass", "next": "/"},
        )
        session_cookie = login_resp.cookies.get(SESSION_COOKIE)

        # Access protected route
        response = client.get("/", cookies={SESSION_COOKIE: session_cookie})
        assert response.status_code == 200
        assert b"Dashboard" in response.content

    def test_invalid_session_cookie_redirected(self):
        response = client.get("/", cookies={SESSION_COOKIE: "bogus-session-id"})
        assert response.status_code == 302
        assert "/auth/login" in response.headers["location"]


# ── Role enforcement tests ───────────────────────────────────────────────────


class TestRoleEnforcement:
    def _login(self, username, password):
        resp = client.post(
            "/auth/login",
            data={"username": username, "password": password, "next": "/"},
        )
        return resp.cookies.get(SESSION_COOKIE)

    def test_admin_can_access_settings(self):
        cookie = self._login("admin", "adminpass")
        response = client.get("/settings", cookies={SESSION_COOKIE: cookie})
        assert response.status_code == 200

    def test_member_cannot_access_settings(self):
        cookie = self._login("member", "memberpass")
        response = client.get("/settings", cookies={SESSION_COOKIE: cookie})
        assert response.status_code == 403

    def test_admin_can_access_roster(self):
        cookie = self._login("admin", "adminpass")
        response = client.get("/roster", cookies={SESSION_COOKIE: cookie})
        assert response.status_code == 200

    def test_member_cannot_access_roster(self):
        cookie = self._login("member", "memberpass")
        response = client.get("/roster", cookies={SESSION_COOKIE: cookie})
        assert response.status_code == 403

    def test_member_can_access_dashboard(self):
        cookie = self._login("member", "memberpass")
        response = client.get("/", cookies={SESSION_COOKIE: cookie})
        assert response.status_code == 200

    def test_member_can_access_actions(self):
        cookie = self._login("member", "memberpass")
        response = client.get("/actions", cookies={SESSION_COOKIE: cookie})
        assert response.status_code == 200


# ── Session cleanup tests ───────────────────────────────────────────────────


class TestSessionCleanup:
    def test_cleanup_removes_expired_sessions(self):
        from intellibox.database import cleanup_expired_sessions

        with override_get_session() as session:
            user = session.query(User).filter_by(username="admin").first()

            # Create an expired session
            expired = UserSession(
                id="expired-session-001",
                user_id=user.id,
                created_at=utcnow() - timedelta(hours=24),
                expires_at=utcnow() - timedelta(hours=16),
            )
            # Create a valid session
            valid = UserSession(
                id="valid-session-001",
                user_id=user.id,
                created_at=utcnow(),
                expires_at=utcnow() + timedelta(hours=8),
            )
            session.add_all([expired, valid])
            session.commit()

            deleted = cleanup_expired_sessions(session)
            session.commit()

            assert deleted == 1
            assert session.query(UserSession).filter_by(id="expired-session-001").first() is None
            assert session.query(UserSession).filter_by(id="valid-session-001").first() is not None
