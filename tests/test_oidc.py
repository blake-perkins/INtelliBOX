"""
Tests for OIDC authentication (AUTH_MODE=oidc).

Covers: role extraction, JIT user provisioning, state cookie security,
OIDC login redirect, callback flow, logout, and login page rendering.

All OIDC provider interactions are mocked — no real IdP needed.
"""

import base64
import json
import os
import tempfile
from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Force AUTH_MODE=oidc with test OIDC config before any app imports
os.environ["AUTH_MODE"] = "oidc"
os.environ["OIDC_ISSUER_URL"] = "https://idp.example.com/realms/test"
os.environ["OIDC_CLIENT_ID"] = "intellibox-test"
os.environ["OIDC_CLIENT_SECRET"] = "test-client-secret"
os.environ["OIDC_ADMIN_ROLE"] = "intellibox-admin"
os.environ["OIDC_ROLES_CLAIM"] = "realm_access.roles"

from intellibox.database import Base
from intellibox.models import User, UserSession
from intellibox.utils.datetime_utils import utcnow
from intellibox.web.auth import SESSION_COOKIE, create_session
from intellibox.web.oidc import (
    _sign,
    _verify_signature,
    determine_role,
    extract_roles,
    load_oidc_state,
    provision_or_update_user,
    save_oidc_state,
)

# ── Test database setup ─────────────────────────────────────────────────────

test_db_fd, test_db_path = tempfile.mkstemp(suffix="_oidc.db", prefix="test_intellibox_")
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

# Mock OIDC metadata so app doesn't try to fetch from real IdP
_FAKE_METADATA = {
    "issuer": "https://idp.example.com/realms/test",
    "authorization_endpoint": "https://idp.example.com/realms/test/protocol/openid-connect/auth",
    "token_endpoint": "https://idp.example.com/realms/test/protocol/openid-connect/token",
    "end_session_endpoint": "https://idp.example.com/realms/test/protocol/openid-connect/logout",
    "jwks_uri": "https://idp.example.com/realms/test/protocol/openid-connect/certs",
}

# Inject metadata directly instead of fetching via HTTP
import intellibox.web.oidc as oidc_module

oidc_module._metadata = _FAKE_METADATA

from fastapi.testclient import TestClient

from intellibox.web.app import app

app.state.oidc_metadata = _FAKE_METADATA
client = TestClient(app, follow_redirects=False)


@pytest.fixture(autouse=True)
def setup_database():
    """Create tables before each test, drop after."""
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


# ── Helper to build a fake ID token ─────────────────────────────────────────

def _make_id_token(claims: dict) -> str:
    """Build a fake JWT (unsigned) from claims dict."""
    header = base64.urlsafe_b64encode(json.dumps({"alg": "RS256"}).encode()).rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    signature = base64.urlsafe_b64encode(b"fake-sig").rstrip(b"=").decode()
    return f"{header}.{payload}.{signature}"


# ── Role extraction tests ──────────────────────────────────────────────────


class TestRoleExtraction:
    def test_keycloak_nested_roles(self):
        claims = {"realm_access": {"roles": ["intellibox-admin", "uma_authorization"]}}
        assert extract_roles(claims) == ["intellibox-admin", "uma_authorization"]

    def test_missing_claim_path_returns_empty(self):
        claims = {"other": "stuff"}
        assert extract_roles(claims) == []

    def test_partial_path_returns_empty(self):
        claims = {"realm_access": "not-a-dict"}
        assert extract_roles(claims) == []

    def test_non_list_value_returns_empty(self):
        claims = {"realm_access": {"roles": "not-a-list"}}
        assert extract_roles(claims) == []

    def test_determine_role_admin(self):
        claims = {"realm_access": {"roles": ["intellibox-admin"]}}
        assert determine_role(claims) == "admin"

    def test_determine_role_member(self):
        claims = {"realm_access": {"roles": ["some-other-role"]}}
        assert determine_role(claims) == "member"

    def test_determine_role_no_roles(self):
        claims = {}
        assert determine_role(claims) == "member"


# ── JIT provisioning tests ─────────────────────────────────────────────────


class TestJITProvisioning:
    def test_new_user_created(self):
        claims = {
            "sub": "oidc-user-001",
            "email": "jane@example.com",
            "name": "Jane Doe",
            "preferred_username": "jdoe",
            "realm_access": {"roles": ["intellibox-admin"]},
        }
        with override_get_session() as session:
            user = provision_or_update_user(claims, session)
            assert user.username == "jdoe"
            assert user.email == "jane@example.com"
            assert user.display_name == "Jane Doe"
            assert user.oidc_sub == "oidc-user-001"
            assert user.role == "admin"
            assert user.password_hash is None
            assert user.is_active is True

    def test_existing_user_found_by_oidc_sub(self):
        with override_get_session() as session:
            session.add(User(
                username="existing",
                email="old@example.com",
                display_name="Old Name",
                oidc_sub="oidc-user-002",
                role="member",
                is_active=True,
            ))
            session.commit()

            claims = {
                "sub": "oidc-user-002",
                "email": "new@example.com",
                "name": "New Name",
                "realm_access": {"roles": ["intellibox-admin"]},
            }
            user = provision_or_update_user(claims, session)
            assert user.username == "existing"  # username unchanged
            assert user.email == "new@example.com"  # updated
            assert user.display_name == "New Name"  # updated
            assert user.role == "admin"  # updated from claims

    def test_existing_local_user_linked_by_email(self):
        with override_get_session() as session:
            session.add(User(
                username="localuser",
                email="shared@example.com",
                display_name="Local User",
                password_hash="bcrypt-hash-here",
                role="member",
                is_active=True,
            ))
            session.commit()

            claims = {
                "sub": "oidc-user-003",
                "email": "shared@example.com",
                "name": "OIDC Name",
                "realm_access": {"roles": []},
            }
            user = provision_or_update_user(claims, session)
            assert user.username == "localuser"
            assert user.oidc_sub == "oidc-user-003"  # linked
            assert user.display_name == "OIDC Name"

    def test_role_updated_on_subsequent_login(self):
        with override_get_session() as session:
            session.add(User(
                username="roleuser",
                email="role@example.com",
                oidc_sub="oidc-user-004",
                role="member",
                is_active=True,
            ))
            session.commit()

            # Login with admin role
            claims = {
                "sub": "oidc-user-004",
                "email": "role@example.com",
                "realm_access": {"roles": ["intellibox-admin"]},
            }
            user = provision_or_update_user(claims, session)
            assert user.role == "admin"

            # Login without admin role
            claims["realm_access"]["roles"] = []
            user = provision_or_update_user(claims, session)
            assert user.role == "member"

    def test_username_collision_gets_suffix(self):
        with override_get_session() as session:
            session.add(User(
                username="jdoe",
                email="existing-jdoe@example.com",
                role="member",
                is_active=True,
            ))
            session.commit()

            claims = {
                "sub": "oidc-user-005",
                "email": "new-jdoe@example.com",
                "preferred_username": "jdoe",
            }
            user = provision_or_update_user(claims, session)
            assert user.username == "jdoe_2"

    def test_last_login_updated(self):
        before = utcnow()
        claims = {
            "sub": "oidc-user-006",
            "email": "time@example.com",
        }
        with override_get_session() as session:
            user = provision_or_update_user(claims, session)
            assert user.last_login is not None
            assert user.last_login >= before


# ── State cookie security tests ────────────────────────────────────────────


class TestStateCookieSecurity:
    def test_sign_and_verify(self):
        signed = _sign("test-data")
        assert _verify_signature(signed) == "test-data"

    def test_tampered_cookie_rejected(self):
        signed = _sign("test-data")
        tampered = signed[:-5] + "XXXXX"
        assert _verify_signature(tampered) is None

    def test_missing_signature_rejected(self):
        assert _verify_signature("no-dot-here") is None

    def test_save_and_load_state_cookie(self):
        from starlette.applications import Starlette
        from starlette.responses import JSONResponse
        from starlette.routing import Route
        from starlette.testclient import TestClient as StarletteTestClient

        # Use a mini app to test cookie round-trip
        async def set_cookie(request):
            response = JSONResponse({"ok": True})
            save_oidc_state(response, "state123", "nonce456", "/next")
            return response

        async def get_cookie(request):
            data = load_oidc_state(request)
            return JSONResponse(data or {})

        mini_app = Starlette(routes=[
            Route("/set", set_cookie),
            Route("/get", get_cookie),
        ])
        mini_client = StarletteTestClient(mini_app)

        # Set the cookie
        resp = mini_client.get("/set")
        assert resp.status_code == 200

        # Read it back
        resp2 = mini_client.get("/get")
        data = resp2.json()
        assert data["state"] == "state123"
        assert data["nonce"] == "nonce456"
        assert data["next"] == "/next"


# ── OIDC login redirect tests ─────────────────────────────────────────────


class TestOIDCLoginRedirect:
    def test_redirects_to_idp(self):
        response = client.get("/auth/oidc/login?next=/actions")
        assert response.status_code == 302
        location = response.headers["location"]
        assert location.startswith("https://idp.example.com/realms/test/protocol/openid-connect/auth")
        assert "client_id=intellibox-test" in location
        assert "response_type=code" in location
        assert "scope=openid+email+profile" in location or "scope=openid%20email%20profile" in location

    def test_state_cookie_set(self):
        response = client.get("/auth/oidc/login?next=/")
        assert "oidc_state" in response.cookies


# ── OIDC callback tests ───────────────────────────────────────────────────


class TestOIDCCallback:
    def _get_login_cookies(self, next_url="/"):
        """Hit /auth/oidc/login and return cookies containing the state."""
        resp = client.get(f"/auth/oidc/login?next={next_url}")
        return resp.cookies, resp.headers["location"]

    def _extract_state_from_url(self, url):
        """Extract the state parameter from an authorization URL."""
        from urllib.parse import parse_qs, urlparse
        params = parse_qs(urlparse(url).query)
        return params["state"][0]

    def test_successful_callback(self):
        cookies, auth_url = self._get_login_cookies("/actions")
        state = self._extract_state_from_url(auth_url)

        fake_claims = {
            "sub": "callback-user-001",
            "email": "callback@example.com",
            "name": "Callback User",
            "iss": "https://idp.example.com/realms/test",
            "aud": "intellibox-test",
            "realm_access": {"roles": ["intellibox-admin"]},
        }
        fake_token_response = {
            "access_token": "fake-access",
            "id_token": _make_id_token(fake_claims),
            "token_type": "Bearer",
        }

        with patch("intellibox.web.oidc.exchange_code_for_tokens", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = fake_token_response
            response = client.get(
                f"/auth/oidc/callback?code=test-code&state={state}",
                cookies=dict(cookies),
            )

        assert response.status_code == 303
        assert response.headers["location"] == "/actions"
        assert SESSION_COOKIE in response.cookies

        # Verify user was provisioned
        with override_get_session() as session:
            user = session.query(User).filter_by(oidc_sub="callback-user-001").first()
            assert user is not None
            assert user.email == "callback@example.com"
            assert user.role == "admin"

    def test_missing_state_cookie(self):
        # Use a fresh client so no cookies leak from prior tests
        fresh_client = TestClient(app, follow_redirects=False)
        response = fresh_client.get("/auth/oidc/callback?code=test&state=bogus")
        assert response.status_code == 303
        assert "expired" in response.headers["location"]

    def test_state_mismatch(self):
        cookies, _ = self._get_login_cookies()
        response = client.get(
            "/auth/oidc/callback?code=test&state=wrong-state",
            cookies=dict(cookies),
        )
        assert response.status_code == 303
        assert "mismatch" in response.headers["location"]

    def test_provider_error(self):
        cookies, auth_url = self._get_login_cookies()
        state = self._extract_state_from_url(auth_url)
        response = client.get(
            f"/auth/oidc/callback?error=access_denied&error_description=User+denied&state={state}",
            cookies=dict(cookies),
        )
        assert response.status_code == 303
        assert "denied" in response.headers["location"].lower()

    def test_no_code_parameter(self):
        cookies, auth_url = self._get_login_cookies()
        state = self._extract_state_from_url(auth_url)
        response = client.get(
            f"/auth/oidc/callback?state={state}",
            cookies=dict(cookies),
        )
        assert response.status_code == 303
        assert "code" in response.headers["location"].lower()

    def test_token_exchange_failure(self):
        cookies, auth_url = self._get_login_cookies()
        state = self._extract_state_from_url(auth_url)

        with patch("intellibox.web.oidc.exchange_code_for_tokens", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.side_effect = Exception("connection refused")
            response = client.get(
                f"/auth/oidc/callback?code=test-code&state={state}",
                cookies=dict(cookies),
            )

        assert response.status_code == 303
        assert "failed" in response.headers["location"].lower()

    def test_session_data_stored(self):
        cookies, auth_url = self._get_login_cookies()
        state = self._extract_state_from_url(auth_url)

        fake_claims = {
            "sub": "session-data-user",
            "email": "sessdata@example.com",
            "iss": "https://idp.example.com/realms/test",
            "aud": "intellibox-test",
            "realm_access": {"roles": ["intellibox-admin"]},
        }
        fake_token_response = {
            "access_token": "fake-access",
            "id_token": _make_id_token(fake_claims),
            "token_type": "Bearer",
        }

        with patch("intellibox.web.oidc.exchange_code_for_tokens", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = fake_token_response
            response = client.get(
                f"/auth/oidc/callback?code=test-code&state={state}",
                cookies=dict(cookies),
            )

        session_id = response.cookies.get(SESSION_COOKIE)
        with override_get_session() as session:
            user_session = session.query(UserSession).filter_by(id=session_id).first()
            assert user_session is not None
            data = json.loads(user_session.session_data)
            assert data["auth_method"] == "oidc"
            assert data["oidc_sub"] == "session-data-user"


# ── OIDC logout tests ─────────────────────────────────────────────────────


class TestOIDCLogout:
    def test_oidc_logout_redirects_to_end_session(self):
        with override_get_session() as session:
            user = User(
                username="logoutuser",
                email="logout@example.com",
                oidc_sub="logout-sub",
                role="member",
                is_active=True,
            )
            session.add(user)
            session.commit()

            session_data = json.dumps({"auth_method": "oidc", "oidc_sub": "logout-sub"})
            session_id = create_session(user.id, session, session_data=session_data)

        response = client.get("/auth/logout", cookies={SESSION_COOKIE: session_id})
        assert response.status_code == 303
        location = response.headers["location"]
        assert "end_session_endpoint" in _FAKE_METADATA
        assert location.startswith(_FAKE_METADATA["end_session_endpoint"])

    def test_local_session_logout_stays_local(self):
        with override_get_session() as session:
            user = User(
                username="locallogout",
                email="locallogout@example.com",
                role="member",
                is_active=True,
            )
            session.add(user)
            session.commit()

            # No session_data (local auth)
            session_id = create_session(user.id, session)

        response = client.get("/auth/logout", cookies={SESSION_COOKIE: session_id})
        assert response.status_code == 303
        assert response.headers["location"] == "/auth/login"

    def test_logout_without_session(self):
        response = client.get("/auth/logout")
        assert response.status_code == 303
        assert response.headers["location"] == "/auth/login"


# ── Login page rendering tests ─────────────────────────────────────────────


class TestLoginPageRendering:
    def test_oidc_mode_shows_sso_button(self):
        response = client.get("/auth/login")
        assert response.status_code == 200
        assert b"Sign in with SSO" in response.content

    def test_oidc_mode_hides_password_form(self):
        response = client.get("/auth/login")
        assert b"Username" not in response.content
        assert b"Password" not in response.content

    def test_oidc_mode_shows_org_subtitle(self):
        response = client.get("/auth/login")
        assert b"organization account" in response.content
