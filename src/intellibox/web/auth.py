"""Authentication and authorization infrastructure.

Provides three AUTH_MODE backends:
  - "disabled" (default): AnonymousAdminUser injected, no login required.
  - "local": Username/password against users table (Phase 2).
  - "oidc": Standard OIDC Authorization Code Flow (Phase 3).
"""

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from intellibox.config import settings

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


# ── Middleware ───────────────────────────────────────────────────────────────

class AuthMiddleware(BaseHTTPMiddleware):
    """Populate ``request.state.user`` on every request.

    When AUTH_MODE is "disabled", every request gets AnonymousAdminUser.
    When auth is enabled (local/oidc), sessions are resolved via a signed
    cookie → user_sessions DB lookup (implemented in Phase 2/3).
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if not settings.auth_enabled:
            request.state.user = _ANONYMOUS
        else:
            # Phase 2/3 will resolve user from session cookie here.
            # For now, fall back to anonymous so the app remains functional
            # during development even if AUTH_MODE is accidentally set.
            request.state.user = None

            # Allow public paths without authentication
            path = request.url.path
            if not any(path.startswith(p) for p in _PUBLIC_PREFIXES):
                if request.state.user is None:
                    # Phase 2 will redirect to /auth/login instead
                    request.state.user = _ANONYMOUS

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
