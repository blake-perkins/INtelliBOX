"""Authentication routes — login, logout."""

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


@router.get("/logout")
async def logout(request: Request):
    """Destroy session and redirect to login."""
    session_id = request.cookies.get(SESSION_COOKIE)
    if session_id:
        with get_session() as db_session:
            destroy_session(session_id, db_session)

    response = RedirectResponse(url="/auth/login", status_code=303)
    response.delete_cookie(key=SESSION_COOKIE)
    return response
