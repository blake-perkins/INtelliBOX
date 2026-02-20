"""Email list, detail, and upload routes."""

import json as _json
from datetime import timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import desc, or_

from intellibox.models import Action, Email
from intellibox.utils.datetime_utils import utcnow
from intellibox.web.deps import get_session, templates
from intellibox.web.queries import get_banner_stats, get_time_since_last_email, paginate

router = APIRouter()

ALLOWED_EMAIL_EXTENSIONS = {".eml", ".msg"}
MAX_EMAIL_FILE_SIZE = 25 * 1024 * 1024  # 25 MB


@router.get("/emails", response_class=HTMLResponse)
async def list_emails(
    request: Request,
    search: Optional[str] = None,
    processed: Optional[str] = None,
    days: Optional[str] = None,
    page: int = Query(1, ge=1)
):
    """List all emails."""
    days_int = int(days) if days and days.strip().isdigit() else None
    with get_session() as session:
        stats = get_banner_stats(session)
        time_since_last_email = get_time_since_last_email(session)

        # Get stats
        total_emails = session.query(Email).count()
        processed_emails = session.query(Email).filter(Email.processed == True).count()
        unprocessed_emails = total_emails - processed_emails

        # Count emails with high priority actions
        emails_with_high_priority = session.query(Email).join(Action).filter(
            Action.priority == "high"
        ).distinct().count()

        # Base query
        query = session.query(Email)

        # Apply filters
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    Email.subject.ilike(search_term),
                    Email.from_address.ilike(search_term),
                    Email.body_text.ilike(search_term)
                )
            )

        if processed == "true":
            query = query.filter(Email.processed == True)
        elif processed == "false":
            query = query.filter(Email.processed == False)

        # Date range filter
        if days_int:
            cutoff_date = utcnow() - timedelta(days=days_int)
            query = query.filter(Email.received_date >= cutoff_date)

        # Order by received date
        query = query.order_by(desc(Email.received_date))

        # Pagination
        emails, total_count, total_pages = paginate(query, page)

        return templates.TemplateResponse("emails.html", {
            "request": request,
            "emails": emails,
            "search": search,
            "processed": processed,
            "days": days,
            "page": page,
            "total_pages": total_pages,
            "total_count": total_count,
            "total_emails": total_emails,
            "processed_emails": processed_emails,
            "unprocessed_emails": unprocessed_emails,
            "emails_with_high_priority": emails_with_high_priority,
            "unassigned_actions": stats["unassigned_actions"],
            "high_priority": stats["high_priority"],
            "overdue_count": stats["overdue_count"],
            "time_since_last_email": time_since_last_email,
            "current_time": utcnow()
        })


@router.post("/emails/upload")
async def upload_email(file: UploadFile = File(...)):
    """Upload an .eml or .msg file for processing."""
    filename = file.filename or "unknown"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EMAIL_EXTENSIONS:
        return RedirectResponse(
            "/emails?upload_error=Unsupported+file+type.+Please+upload+.eml+or+.msg",
            status_code=303,
        )

    content = await file.read()
    if len(content) > MAX_EMAIL_FILE_SIZE:
        return RedirectResponse(
            "/emails?upload_error=File+too+large.+Maximum+size+is+25+MB",
            status_code=303,
        )
    if len(content) == 0:
        return RedirectResponse(
            "/emails?upload_error=File+is+empty",
            status_code=303,
        )

    inbox_dir = Path("data/inbox")
    inbox_dir.mkdir(parents=True, exist_ok=True)
    dest = inbox_dir / filename

    # Avoid overwriting existing files
    if dest.exists():
        stem = dest.stem
        suffix = dest.suffix
        counter = 1
        while dest.exists():
            dest = inbox_dir / f"{stem}_{counter}{suffix}"
            counter += 1

    dest.write_bytes(content)
    return RedirectResponse("/emails?uploaded=1", status_code=303)


@router.get("/emails/{email_id}", response_class=HTMLResponse)
async def view_email(request: Request, email_id: int):
    """View details of a specific email."""
    with get_session() as session:
        email = session.query(Email).filter_by(id=email_id).first()

        if not email:
            raise HTTPException(status_code=404, detail="Email not found")

        # Get associated actions
        actions = session.query(Action).filter_by(email_id=email_id).all()

        # Count actions by status
        assigned_count = sum(1 for action in actions if action.assignments)
        unassigned_count = len(actions) - assigned_count
        completed_count = sum(1 for action in actions if action.assignments and action.assignments[0].status == 'completed')

        # Count by priority
        high_priority_count = sum(1 for action in actions if action.priority == 'high')

        # Parse also_received_from JSON for template
        also_received = _json.loads(email.also_received_from) if email.also_received_from else []

        return templates.TemplateResponse("email_detail.html", {
            "request": request,
            "email": email,
            "actions": actions,
            "assigned_count": assigned_count,
            "unassigned_count": unassigned_count,
            "completed_count": completed_count,
            "high_priority_count": high_priority_count,
            "also_received": also_received,
            "current_time": utcnow()
        })
