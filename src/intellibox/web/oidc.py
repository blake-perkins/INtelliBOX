"""OIDC client initialization and helpers.

Handles the Authorization Code Flow using authlib's httpx-based async client.
Provider-agnostic — works with Keycloak, Azure AD, Okta, etc.
"""

import hashlib
import hmac
import json
import secrets
from typing import Optional
from urllib.parse import urlencode

import httpx

from intellibox.config import settings
from intellibox.utils.datetime_utils import utcnow

# ── OIDC metadata (populated at startup by init_oidc) ─────────────────────

_metadata: dict = {}


async def init_oidc(app) -> None:
    """Fetch OIDC discovery metadata and store on app.state.

    Called from app.py lifespan when auth_mode=oidc.
    """
    global _metadata
    discovery_url = f"{settings.oidc_issuer_url.rstrip('/')}/.well-known/openid-configuration"

    async with httpx.AsyncClient() as client:
        resp = await client.get(discovery_url, timeout=10)
        resp.raise_for_status()
        _metadata = resp.json()

    app.state.oidc_metadata = _metadata


def get_metadata() -> dict:
    """Return the cached OIDC discovery metadata."""
    if not _metadata:
        raise RuntimeError("OIDC not initialized. Is AUTH_MODE=oidc?")
    return _metadata


# ── Authorization URL builder ──────────────────────────────────────────────

def build_authorization_url(redirect_uri: str, state: str, nonce: str) -> str:
    """Build the OIDC authorization URL for the redirect."""
    meta = get_metadata()
    params = {
        "response_type": "code",
        "client_id": settings.oidc_client_id,
        "redirect_uri": redirect_uri,
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
    }
    return f"{meta['authorization_endpoint']}?{urlencode(params)}"


# ── Token exchange ─────────────────────────────────────────────────────────

async def exchange_code_for_tokens(code: str, redirect_uri: str) -> dict:
    """Exchange an authorization code for tokens via back-channel POST."""
    meta = get_metadata()
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": settings.oidc_client_id,
        "client_secret": settings.oidc_client_secret,
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(meta["token_endpoint"], data=data, timeout=10)
        resp.raise_for_status()
        return resp.json()


def decode_id_token(token_response: dict) -> dict:
    """Decode the ID token claims (without full signature verification).

    In production behind a trusted IdP, the token was received directly
    from the token endpoint over TLS (back-channel), so signature
    verification is optional per the OIDC spec (section 3.1.3.7).
    We still validate issuer and audience.
    """
    import base64

    id_token = token_response.get("id_token", "")
    if not id_token:
        raise ValueError("No id_token in token response")

    # Decode the payload (second segment)
    parts = id_token.split(".")
    if len(parts) != 3:
        raise ValueError("Malformed id_token")

    payload = parts[1]
    # Add padding
    payload += "=" * (4 - len(payload) % 4)
    claims = json.loads(base64.urlsafe_b64decode(payload))

    # Validate issuer
    expected_issuer = settings.oidc_issuer_url.rstrip("/")
    if claims.get("iss", "").rstrip("/") != expected_issuer:
        raise ValueError(
            f"ID token issuer mismatch: {claims.get('iss')} != {expected_issuer}"
        )

    # Validate audience
    aud = claims.get("aud")
    if isinstance(aud, list):
        if settings.oidc_client_id not in aud:
            raise ValueError("ID token audience mismatch")
    elif aud != settings.oidc_client_id:
        raise ValueError("ID token audience mismatch")

    return claims


# ── State/nonce cookie helpers ─────────────────────────────────────────────

_STATE_COOKIE = "oidc_state"
_STATE_MAX_AGE = 300  # 5 minutes


def _sign(data: str) -> str:
    """HMAC-sign a string using the app secret_key."""
    sig = hmac.new(
        settings.secret_key.encode(), data.encode(), hashlib.sha256
    ).hexdigest()
    return f"{data}.{sig}"


def _verify_signature(signed: str) -> Optional[str]:
    """Verify HMAC signature. Returns data or None."""
    if "." not in signed:
        return None
    data, sig = signed.rsplit(".", 1)
    expected = hmac.new(
        settings.secret_key.encode(), data.encode(), hashlib.sha256
    ).hexdigest()
    if hmac.compare_digest(sig, expected):
        return data
    return None


def generate_state_and_nonce() -> tuple[str, str]:
    """Generate cryptographic state and nonce values."""
    return secrets.token_urlsafe(32), secrets.token_urlsafe(32)


def save_oidc_state(response, state: str, nonce: str, next_url: str) -> None:
    """Store OIDC state, nonce, and next_url in a signed cookie."""
    payload = json.dumps({"state": state, "nonce": nonce, "next": next_url})
    signed = _sign(payload)
    response.set_cookie(
        key=_STATE_COOKIE,
        value=signed,
        httponly=True,
        samesite="lax",
        max_age=_STATE_MAX_AGE,
    )


def load_oidc_state(request) -> Optional[dict]:
    """Read and verify the OIDC state cookie. Returns dict or None."""
    raw = request.cookies.get(_STATE_COOKIE)
    if not raw:
        return None
    data = _verify_signature(raw)
    if not data:
        return None
    try:
        return json.loads(data)
    except (json.JSONDecodeError, TypeError):
        return None


def clear_oidc_state(response) -> None:
    """Delete the OIDC state cookie."""
    response.delete_cookie(key=_STATE_COOKIE)


# ── Role extraction ────────────────────────────────────────────────────────

def extract_roles(claims: dict) -> list[str]:
    """Extract roles from ID token claims using the configured dot-path.

    Example: oidc_roles_claim="realm_access.roles"
    Claims: {"realm_access": {"roles": ["intellibox-admin", "uma_authorization"]}}
    Returns: ["intellibox-admin", "uma_authorization"]
    """
    parts = settings.oidc_roles_claim.split(".")
    value = claims
    for part in parts:
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return []
    return value if isinstance(value, list) else []


def determine_role(claims: dict) -> str:
    """Determine INtelliBOX role (admin/member) from OIDC claims."""
    roles = extract_roles(claims)
    if settings.oidc_admin_role in roles:
        return "admin"
    return "member"


# ── JIT user provisioning ─────────────────────────────────────────────────

def provision_or_update_user(claims: dict, db_session):
    """Find or create a user from OIDC claims. Update attributes on each login.

    Claims expected:
      - sub (required): OIDC subject identifier
      - email: user email
      - name or preferred_username: display name
    """
    from intellibox.models import User

    sub = claims["sub"]
    email = claims.get("email", "")
    display_name = claims.get("name") or claims.get("preferred_username") or email
    username = claims.get("preferred_username") or email.split("@")[0] if email else sub
    role = determine_role(claims)

    # Try to find by oidc_sub first
    user = db_session.query(User).filter(User.oidc_sub == sub).first()
    if user:
        user.email = email
        user.display_name = display_name
        user.role = role
        user.last_login = utcnow()
        db_session.commit()
        return user

    # Try to find by email (link existing local user to OIDC)
    if email:
        user = db_session.query(User).filter(User.email == email).first()
        if user:
            user.oidc_sub = sub
            user.display_name = display_name
            user.role = role
            user.last_login = utcnow()
            db_session.commit()
            return user

    # JIT provision new user — handle username collisions
    user = _create_user_with_unique_username(
        db_session, username=username, email=email,
        display_name=display_name, role=role, oidc_sub=sub,
    )
    return user


def _create_user_with_unique_username(db_session, *, username, email, display_name, role, oidc_sub):
    """Create a new user, appending a suffix if username is taken."""
    from intellibox.models import User

    candidate = username
    suffix = 1
    while db_session.query(User).filter(User.username == candidate).first():
        suffix += 1
        candidate = f"{username}_{suffix}"

    user = User(
        username=candidate,
        email=email,
        display_name=display_name,
        password_hash=None,
        role=role,
        oidc_sub=oidc_sub,
        is_active=True,
        last_login=utcnow(),
    )
    db_session.add(user)
    db_session.commit()
    return user
