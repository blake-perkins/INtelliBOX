"""Authentication and authorization infrastructure.

Provides three AUTH_MODE backends:
  - "disabled" (default): AnonymousAdminUser injected, no login required.
  - "local": Username/password against users table.
  - "oidc": Standard OIDC Authorization Code Flow (Phase 3).
"""

import uuid
from datetime import timedelta

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import RedirectResponse, Response

from intellibox.config import settings
from intellibox.utils.datetime_utils import utcnow

# ── Anonymous user (AUTH_MODE=disabled) ──────────────────────────────────────

class AnonymousAdminUser:
    """Synthetic user injected when authentication is disabled."""

    id = 0
    username = "local"
    email = ""
    display_name = "Local Admin"
    role = "admin"
    is_active = True
    is_anonymous = True
    roster_member = None
    roster_member_id = None


_ANONYMOUS = AnonymousAdminUser()

# Paths that never require authentication
_PUBLIC_PREFIXES = ("/auth/", "/health", "/static/", "/api/stats")

# Cookie name for session ID
SESSION_COOKIE = "intellibox_session"


# ── Password hashing ────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    from passlib.hash import bcrypt

    return bcrypt.using(rounds=12).hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    from passlib.hash import bcrypt

    return bcrypt.verify(password, password_hash)


# ── Session management ──────────────────────────────────────────────────────

def create_session(user_id: int, db_session) -> str:
    """Create a new server-side session and return the session ID."""
    from intellibox.models import UserSession

    session_id = str(uuid.uuid4())
    now = utcnow()
    expires = now + timedelta(hours=settings.session_ttl_hours)

    db_session.add(UserSession(
        id=session_id,
        user_id=user_id,
        created_at=now,
        expires_at=expires,
    ))
    db_session.commit()
    return session_id


def resolve_user_from_session(session_id: str, db_session):
    """Look up a session and return the associated User, or None."""
    from intellibox.models import User, UserSession

    if not session_id:
        return None

    user_session = (
        db_session.query(UserSession)
        .filter(UserSession.id == session_id, UserSession.expires_at > utcnow())
        .first()
    )
    if not user_session:
        return None

    user = db_session.query(User).filter(User.id == user_session.user_id, User.is_active == True).first()  # noqa: E712
    return user


def destroy_session(session_id: str, db_session) -> None:
    """Delete a session row from the database."""
    from intellibox.models import UserSession

    db_session.query(UserSession).filter(UserSession.id == session_id).delete()
    db_session.commit()


# ── Middleware ───────────────────────────────────────────────────────────────

class AuthMiddleware(BaseHTTPMiddleware):
    """Populate ``request.state.user`` on every request.

    When AUTH_MODE is "disabled", every request gets AnonymousAdminUser.
    When auth is enabled (local/oidc), sessions are resolved via a signed
    cookie → user_sessions DB lookup.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if not settings.auth_enabled:
            request.state.user = _ANONYMOUS
        else:
            # Resolve user from session cookie
            import intellibox.database as _database

            session_id = request.cookies.get(SESSION_COOKIE)
            user = None
            if session_id:
                with _database.get_session() as db_session:
                    user = resolve_user_from_session(session_id, db_session)
                    # Detach from session so it's usable after context closes
                    if user:
                        db_session.expunge(user)

            request.state.user = user

            # Redirect unauthenticated requests to login (except public paths)
            path = request.url.path
            if not any(path.startswith(p) for p in _PUBLIC_PREFIXES):
                if request.state.user is None:
                    return RedirectResponse(
                        url=f"/auth/login?next={path}",
                        status_code=302,
                    )

        return await call_next(request)


# ── Dependencies for route-level enforcement ────────────────────────────────

def require_auth(request: Request):
    """FastAPI dependency: ensure the request has an authenticated user."""
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def require_admin(request: Request):
    """FastAPI dependency: ensure the request has an admin user."""
    user = require_auth(request)
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
