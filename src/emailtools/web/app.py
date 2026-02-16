"""FastAPI web application for EmailTools."""

from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, func, case

from emailtools.database import get_session
from emailtools.models import Action, Assignment, Email, ProcessingLog
from emailtools.reporter.generator import generate_report_data

# Create FastAPI app
app = FastAPI(
    title="EmailTools",
    description="AI-Powered Email Action Tracking System",
    version="1.0.0"
)

# Setup templates
template_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(template_dir))


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard showing summary statistics."""
    with get_session() as session:
        # Get statistics
        total_emails = session.query(Email).count()
        total_actions = session.query(Action).count()

        unassigned_actions = session.query(Action).outerjoin(Assignment).filter(
            Assignment.id.is_(None)
        ).count()

        high_priority = session.query(Action).outerjoin(Assignment).filter(
            Assignment.id.is_(None),
            Action.priority == "high"
        ).count()

        # Get recent actions (last 7 days)
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_actions = session.query(Action).filter(
            Action.created_at >= week_ago
        ).count()

        # Get overdue actions
        today = datetime.utcnow().date()
        overdue_count = session.query(Action).outerjoin(Assignment).filter(
            Assignment.id.is_(None),
            Action.due_date < today
        ).count()

        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "total_emails": total_emails,
            "total_actions": total_actions,
            "unassigned_actions": unassigned_actions,
            "high_priority": high_priority,
            "recent_actions": recent_actions,
            "overdue_count": overdue_count
        })


@app.get("/actions", response_class=HTMLResponse)
async def list_actions(
    request: Request,
    priority: Optional[str] = None,
    assigned: Optional[bool] = None,
    page: int = Query(1, ge=1)
):
    """List all actions with filtering."""
    with get_session() as session:
        # Base query
        query = session.query(Action).outerjoin(Assignment).join(Email)

        # Apply filters
        if priority:
            query = query.filter(Action.priority == priority)

        if assigned is not None:
            if assigned:
                query = query.filter(Assignment.id.isnot(None))
            else:
                query = query.filter(Assignment.id.is_(None))

        # Order by priority and due date
        priority_order = case(
            (Action.priority == "high", 1),
            (Action.priority == "medium", 2),
            (Action.priority == "low", 3),
            else_=4
        )
        query = query.order_by(priority_order, Action.due_date.asc().nullslast())

        # Pagination
        per_page = 50
        total_count = query.count()
        total_pages = (total_count + per_page - 1) // per_page

        actions = query.offset((page - 1) * per_page).limit(per_page).all()

        return templates.TemplateResponse("actions.html", {
            "request": request,
            "actions": actions,
            "priority_filter": priority,
            "assigned_filter": assigned,
            "page": page,
            "total_pages": total_pages,
            "total_count": total_count
        })


@app.get("/actions/{action_id}", response_class=HTMLResponse)
async def view_action(request: Request, action_id: int):
    """View details of a specific action."""
    with get_session() as session:
        action = session.query(Action).filter_by(id=action_id).first()

        if not action:
            raise HTTPException(status_code=404, detail="Action not found")

        # Get assignment if exists
        assignment = session.query(Assignment).filter_by(action_id=action_id).first()

        return templates.TemplateResponse("action_detail.html", {
            "request": request,
            "action": action,
            "assignment": assignment
        })


@app.get("/emails", response_class=HTMLResponse)
async def list_emails(request: Request, page: int = Query(1, ge=1)):
    """List all emails."""
    with get_session() as session:
        # Pagination
        per_page = 50
        total_count = session.query(Email).count()
        total_pages = (total_count + per_page - 1) // per_page

        emails = session.query(Email).order_by(
            desc(Email.received_date)
        ).offset((page - 1) * per_page).limit(per_page).all()

        return templates.TemplateResponse("emails.html", {
            "request": request,
            "emails": emails,
            "page": page,
            "total_pages": total_pages,
            "total_count": total_count
        })


@app.get("/emails/{email_id}", response_class=HTMLResponse)
async def view_email(request: Request, email_id: int):
    """View details of a specific email."""
    with get_session() as session:
        email = session.query(Email).filter_by(id=email_id).first()

        if not email:
            raise HTTPException(status_code=404, detail="Email not found")

        # Get associated actions
        actions = session.query(Action).filter_by(email_id=email_id).all()

        return templates.TemplateResponse("email_detail.html", {
            "request": request,
            "email": email,
            "actions": actions
        })


@app.get("/report", response_class=HTMLResponse)
async def view_report(request: Request):
    """View the daily report."""
    with get_session() as session:
        report_data = generate_report_data(session)

        return templates.TemplateResponse("report.html", {
            "request": request,
            "report": report_data
        })


@app.get("/api/stats")
async def get_stats():
    """API endpoint for statistics (for auto-refresh)."""
    with get_session() as session:
        return {
            "total_emails": session.query(Email).count(),
            "total_actions": session.query(Action).count(),
            "unassigned_actions": session.query(Action).outerjoin(Assignment).filter(
                Assignment.id.is_(None)
            ).count(),
            "high_priority": session.query(Action).outerjoin(Assignment).filter(
                Assignment.id.is_(None),
                Action.priority == "high"
            ).count()
        }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
