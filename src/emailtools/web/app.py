"""FastAPI web application for EmailTools."""

from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Request, HTTPException, Query, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, func, case

from emailtools.database import get_session
from emailtools.models import Action, Assignment, Email, ProcessingLog
from emailtools.reporter.generator import generate_report_data
from emailtools.config import settings

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

        # Priority breakdown for unassigned actions
        high_priority = session.query(Action).outerjoin(Assignment).filter(
            Assignment.id.is_(None),
            Action.priority == "high"
        ).count()

        medium_priority = session.query(Action).outerjoin(Assignment).filter(
            Assignment.id.is_(None),
            Action.priority == "medium"
        ).count()

        low_priority = session.query(Action).outerjoin(Assignment).filter(
            Assignment.id.is_(None),
            Action.priority == "low"
        ).count()

        # Assignment statistics
        assigned_actions = session.query(Action).join(Assignment).count()

        completed_actions = session.query(Action).join(Assignment).filter(
            Assignment.status == "completed"
        ).count()

        in_progress_actions = session.query(Action).join(Assignment).filter(
            Assignment.status.in_(["assigned", "in_progress"])
        ).count()

        # Get recent actions (last 7 days)
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_actions_count = session.query(Action).filter(
            Action.created_at >= week_ago
        ).count()

        # Get overdue unassigned actions
        today = datetime.utcnow().date()
        overdue_actions = session.query(Action).outerjoin(Assignment).join(Email).filter(
            Assignment.id.is_(None),
            Action.due_date < today
        ).order_by(Action.due_date).limit(5).all()

        # Get high priority unassigned actions
        high_priority_actions = session.query(Action).outerjoin(Assignment).join(Email).filter(
            Assignment.id.is_(None),
            Action.priority == "high"
        ).order_by(Action.due_date.asc().nullslast()).limit(5).all()

        # Get recent assignments (last 5)
        recent_assignments = session.query(Assignment, Action).join(
            Action
        ).order_by(desc(Assignment.assigned_at)).limit(5).all()

        # Get recently completed (last 5)
        recent_completions = session.query(Assignment, Action).join(
            Action
        ).filter(
            Assignment.status == "completed"
        ).order_by(desc(Assignment.assigned_at)).limit(5).all()

        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "total_emails": total_emails,
            "total_actions": total_actions,
            "unassigned_actions": unassigned_actions,
            "assigned_actions": assigned_actions,
            "completed_actions": completed_actions,
            "in_progress_actions": in_progress_actions,
            "high_priority": high_priority,
            "medium_priority": medium_priority,
            "low_priority": low_priority,
            "recent_actions_count": recent_actions_count,
            "overdue_actions": overdue_actions,
            "high_priority_actions": high_priority_actions,
            "recent_assignments": recent_assignments,
            "recent_completions": recent_completions,
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
            "assignment": assignment,
            "team_members": settings.get_team_members()
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


@app.post("/actions/{action_id}/assign")
async def assign_action(
    action_id: int,
    assigned_to: str = Form(...),
    notes: str = Form(""),
):
    """Assign an action to someone."""
    with get_session() as session:
        action = session.query(Action).filter_by(id=action_id).first()
        if not action:
            raise HTTPException(status_code=404, detail="Action not found")

        # Check if already assigned
        existing = session.query(Assignment).filter_by(action_id=action_id).first()

        if existing:
            # Update existing assignment
            existing.assigned_to = assigned_to
            existing.notes = notes
            existing.assigned_at = datetime.utcnow()
        else:
            # Create new assignment
            assignment = Assignment(
                action_id=action_id,
                assigned_to=assigned_to,
                notes=notes,
                status="assigned"
            )
            session.add(assignment)

        session.commit()

    return RedirectResponse(url=f"/actions/{action_id}", status_code=303)


@app.post("/actions/{action_id}/priority")
async def update_priority(
    action_id: int,
    priority: str = Form(...),
):
    """Update action priority."""
    with get_session() as session:
        action = session.query(Action).filter_by(id=action_id).first()
        if not action:
            raise HTTPException(status_code=404, detail="Action not found")

        if priority not in ["high", "medium", "low"]:
            raise HTTPException(status_code=400, detail="Invalid priority")

        action.priority = priority
        session.commit()

    return RedirectResponse(url=f"/actions/{action_id}", status_code=303)


@app.post("/actions/{action_id}/due-date")
async def update_due_date(
    action_id: int,
    due_date: str = Form(""),
):
    """Update action due date."""
    with get_session() as session:
        action = session.query(Action).filter_by(id=action_id).first()
        if not action:
            raise HTTPException(status_code=404, detail="Action not found")

        # Parse date or clear if empty
        if due_date:
            from datetime import datetime as dt
            try:
                action.due_date = dt.strptime(due_date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format")
        else:
            action.due_date = None

        session.commit()

    return RedirectResponse(url=f"/actions/{action_id}", status_code=303)


@app.post("/actions/{action_id}/complete")
async def complete_action(action_id: int):
    """Mark an action as completed."""
    with get_session() as session:
        assignment = session.query(Assignment).filter_by(action_id=action_id).first()

        if not assignment:
            # Create assignment with completed status
            assignment = Assignment(
                action_id=action_id,
                assigned_to="Unknown",
                status="completed"
            )
            session.add(assignment)
        else:
            assignment.status = "completed"

        session.commit()

    return RedirectResponse(url=f"/actions/{action_id}", status_code=303)


@app.post("/actions/{action_id}/unassign")
async def unassign_action(action_id: int):
    """Remove assignment from an action."""
    with get_session() as session:
        assignment = session.query(Assignment).filter_by(action_id=action_id).first()

        if assignment:
            session.delete(assignment)
            session.commit()

    return RedirectResponse(url=f"/actions/{action_id}", status_code=303)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
