"""Authentication routes — login, logout, OIDC."""

import json

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from intellibox.config import settings
from intellibox.models import User
from intellibox.utils.datetime_utils import utcnow
from intellibox.web.auth import (
    SESSION_COOKIE,
    create_session,
    destroy_session,
    verify_password,
)
from intellibox.web.deps import get_session, templates

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, next: str = "/", error: str = ""):
    """Render the login form."""
    return templates.TemplateResponse("login.html", {
        "request": request,
        "next": next,
        "error": error,
        "auth_mode": settings.auth_mode,
    })


@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
):
    """Validate credentials, create session, redirect."""
    with get_session() as db_session:
        user = (
            db_session.query(User)
            .filter(User.username == username, User.is_active == True)  # noqa: E712
            .first()
        )

        if not user or not user.password_hash or not verify_password(password, user.password_hash):
            return RedirectResponse(
                url=f"/auth/login?next={next}&error=Invalid+username+or+password",
                status_code=303,
            )

        # Update last_login
        user.last_login = utcnow()
        db_session.commit()

        # Create server-side session
        session_id = create_session(user.id, db_session)

    # Set session cookie and redirect
    safe_next = next if next.startswith("/") else "/"
    response = RedirectResponse(url=safe_next, status_code=303)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=session_id,
        httponly=True,
        samesite="lax",
        max_age=settings.session_ttl_hours * 3600,
    )
    return response


# ── OIDC routes ────────────────────────────────────────────────────────────

@router.get("/oidc/login")
async def oidc_login(request: Request, next: str = "/"):
    """Initiate OIDC Authorization Code Flow."""
    from intellibox.web.oidc import (
        build_authorization_url,
        generate_state_and_nonce,
        save_oidc_state,
    )

    state, nonce = generate_state_and_nonce()
    redirect_uri = str(request.url_for("oidc_callback"))
    authorization_url = build_authorization_url(redirect_uri, state, nonce)

    response = RedirectResponse(url=authorization_url, status_code=302)
    save_oidc_state(response, state, nonce, next)
    return response


@router.get("/oidc/callback")
async def oidc_callback(request: Request):
    """Handle OIDC provider callback: exchange code, provision user, create session."""
    from intellibox.web.oidc import (
        clear_oidc_state,
        decode_id_token,
        exchange_code_for_tokens,
        extract_roles,
        load_oidc_state,
        provision_or_update_user,
    )

    # 1. Validate state
    saved = load_oidc_state(request)
    if not saved:
        return RedirectResponse(
            url="/auth/login?error=OIDC+session+expired.+Please+try+again.",
            status_code=303,
        )

    callback_state = request.query_params.get("state")
    if callback_state != saved["state"]:
        return RedirectResponse(
            url="/auth/login?error=OIDC+state+mismatch.",
            status_code=303,
        )

    # 2. Check for error response from provider
    error = request.query_params.get("error")
    if error:
        desc = request.query_params.get("error_description", error)
        return RedirectResponse(
            url=f"/auth/login?error={desc}",
            status_code=303,
        )

    # 3. Exchange code for tokens
    code = request.query_params.get("code")
    if not code:
        return RedirectResponse(
            url="/auth/login?error=No+authorization+code+received.",
            status_code=303,
        )

    redirect_uri = str(request.url_for("oidc_callback"))
    try:
        token_response = await exchange_code_for_tokens(code, redirect_uri)
    except Exception as exc:
        return RedirectResponse(
            url=f"/auth/login?error=Token+exchange+failed:+{exc}",
            status_code=303,
        )

    # 4. Decode and validate ID token
    try:
        claims = decode_id_token(token_response)
    except ValueError as exc:
        return RedirectResponse(
            url=f"/auth/login?error={exc}",
            status_code=303,
        )

    if "sub" not in claims:
        return RedirectResponse(
            url="/auth/login?error=No+user+info+in+OIDC+response.",
            status_code=303,
        )

    # 5. JIT provision or update user
    with get_session() as db_session:
        user = provision_or_update_user(claims, db_session)

        session_data = json.dumps({
            "auth_method": "oidc",
            "oidc_sub": claims["sub"],
            "oidc_roles": extract_roles(claims),
        })
        session_id = create_session(user.id, db_session, session_data=session_data)

    # 6. Set cookie and redirect
    safe_next = saved.get("next", "/")
    if not safe_next.startswith("/"):
        safe_next = "/"

    response = RedirectResponse(url=safe_next, status_code=303)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=session_id,
        httponly=True,
        samesite="lax",
        max_age=settings.session_ttl_hours * 3600,
    )
    clear_oidc_state(response)
    return response


# ── Logout (supports both local and OIDC) ─────────────────────────────────

@router.get("/logout")
async def logout(request: Request):
    """Destroy session and redirect. For OIDC, redirect to end_session_endpoint."""
    session_id = request.cookies.get(SESSION_COOKIE)
    session_data = None

    if session_id:
        with get_session() as db_session:
            from intellibox.models import UserSession

            user_session = db_session.query(UserSession).filter_by(id=session_id).first()
            if user_session and user_session.session_data:
                try:
                    session_data = json.loads(user_session.session_data)
                except json.JSONDecodeError:
                    pass
            destroy_session(session_id, db_session)

    response = RedirectResponse(url="/auth/login", status_code=303)
    response.delete_cookie(key=SESSION_COOKIE)

    # RP-initiated logout: redirect to OIDC end_session_endpoint if available
    if (
        session_data
        and session_data.get("auth_method") == "oidc"
        and settings.auth_mode == "oidc"
    ):
        try:
            from intellibox.web.oidc import get_metadata

            metadata = get_metadata()
            end_session_url = metadata.get("end_session_endpoint")
            if end_session_url:
                post_logout_uri = str(request.url_for("login_page"))
                response = RedirectResponse(
                    url=f"{end_session_url}?post_logout_redirect_uri={post_logout_uri}",
                    status_code=303,
                )
                response.delete_cookie(key=SESSION_COOKIE)
        except Exception:
            pass  # Fall through to local logout

    return response
