"""Action CRUD and management routes."""

import csv
import io
from typing import Optional

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import case, desc, func, or_
from sqlalchemy.orm import Session, contains_eager, subqueryload

from intellibox.audit import log_audit
from intellibox.knowledge import search_knowledge_base
from intellibox.models import Action, Assignment, Email
from intellibox.settings_service import SettingsService
from intellibox.utils.datetime_utils import utcnow
from intellibox.web.deps import get_session, templates
from intellibox.web.queries import get_active_roster, paginate

router = APIRouter()


def _build_actions_query(
    session: Session,
    *,
    priority: Optional[str] = None,
    assigned: Optional[str] = None,
    completed: Optional[str] = None,
    assignee: Optional[str] = None,
    search: Optional[str] = None,
    overdue: Optional[str] = None,
):
    """Build a filtered and sorted actions query.

    Shared by the actions list page and CSV export endpoint.
    Returns the query (caller handles pagination or .all()).
    """
    today = utcnow().date()

    query = session.query(Action).options(
        subqueryload(Action.assignments),
        contains_eager(Action.email),
    ).outerjoin(Assignment).join(Action.email)

    if priority:
        query = query.filter(Action.priority == priority)

    if completed == "true" or assigned == "completed":
        query = query.filter(Assignment.status == "completed")
    elif assigned == "true":
        query = query.filter(Assignment.id.isnot(None))
    elif assigned == "false":
        query = query.filter(Assignment.id.is_(None))

    if assignee:
        query = query.filter(Assignment.assigned_to == assignee)

    if overdue == "true":
        query = query.filter(Action.due_date < today)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Action.title.ilike(search_term),
                Action.description.ilike(search_term),
                Email.subject.ilike(search_term)
            )
        )

    priority_order = case(
        (Action.priority == "high", 1),
        (Action.priority == "medium", 2),
        (Action.priority == "low", 3),
        else_=4
    )
    query = query.order_by(priority_order, Action.due_date.asc().nullslast())

    return query


@router.get("/actions", response_class=HTMLResponse)
async def list_actions(
    request: Request,
    priority: Optional[str] = None,
    assigned: Optional[str] = None,
    completed: Optional[str] = None,
    assignee: Optional[str] = None,
    search: Optional[str] = None,
    overdue: Optional[str] = None,
    page: int = Query(1, ge=1)
):
    """List all actions with filtering."""
    with get_session() as session:
        # Get stats for header — single aggregated query
        today = utcnow().date()
        action_stats = session.query(
            func.count(Action.id).label("total"),
            func.count(case((Assignment.id.is_(None), Action.id))).label("unassigned"),
            func.count(case(((Assignment.id.is_(None)) & (Action.priority == "high"), Action.id))).label("high"),
            func.count(case(((Assignment.id.is_(None)) & (Action.priority == "medium"), Action.id))).label("medium"),
            func.count(case(((Assignment.id.is_(None)) & (Action.priority == "low"), Action.id))).label("low"),
            func.count(case((
                (Action.due_date < today) & ((Assignment.id.is_(None)) | (Assignment.status != "completed")), Action.id
            ))).label("overdue"),
        ).select_from(Action).outerjoin(Assignment).one()

        total_actions = action_stats.total
        unassigned_actions = action_stats.unassigned
        high_priority = action_stats.high
        medium_priority = action_stats.medium
        low_priority = action_stats.low
        overdue_count = action_stats.overdue

        query = _build_actions_query(
            session,
            priority=priority,
            assigned=assigned,
            completed=completed,
            assignee=assignee,
            search=search,
            overdue=overdue,
        )

        # Pagination
        actions, total_count, total_pages = paginate(query, page)

        # Get list of assignees for filter dropdown
        assignees = session.query(Assignment.assigned_to).distinct().order_by(Assignment.assigned_to).all()
        assignee_list = [a[0] for a in assignees if a[0]]

        # Get roster members for Quick Assign dropdown
        roster = get_active_roster(session)

        return templates.TemplateResponse("actions.html", {
            "request": request,
            "actions": actions,
            "priority": priority,
            "assigned": assigned,
            "completed": completed,
            "assignee": assignee,
            "search": search,
            "page": page,
            "total_pages": total_pages,
            "total_count": total_count,
            "total_actions": total_actions,
            "unassigned_actions": unassigned_actions,
            "high_priority": high_priority,
            "medium_priority": medium_priority,
            "low_priority": low_priority,
            "overdue_count": overdue_count,
            "overdue": overdue,
            "assignee_list": assignee_list,
            "roster": roster,
            "current_time": utcnow()
        })


@router.get("/actions/export.csv")
async def export_actions_csv(
    priority: Optional[str] = None,
    assigned: Optional[str] = None,
    completed: Optional[str] = None,
    assignee: Optional[str] = None,
    search: Optional[str] = None,
    overdue: Optional[str] = None,
):
    """Export actions to CSV with the same filters as the actions list."""
    with get_session() as session:
        query = _build_actions_query(
            session,
            priority=priority,
            assigned=assigned,
            completed=completed,
            assignee=assignee,
            search=search,
            overdue=overdue,
        )
        actions = query.all()

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "ID", "Title", "Description", "Priority", "Due Date",
            "Category", "Assignee", "Status", "Email Subject",
            "Email From", "Email Received", "Created At",
        ])
        for action in actions:
            assignment = action.assignments[0] if action.assignments else None
            writer.writerow([
                action.id,
                action.title,
                action.description or "",
                action.priority or "",
                action.due_date.strftime("%Y-%m-%d") if action.due_date else "",
                action.category or "",
                assignment.assigned_to if assignment else "",
                assignment.status if assignment else "unassigned",
                action.email.subject,
                action.email.from_address,
                action.email.received_date.strftime("%Y-%m-%d") if action.email.received_date else "",
                action.created_at.strftime("%Y-%m-%d %H:%M") if action.created_at else "",
            ])

    filename = f"actions_{utcnow().strftime('%Y-%m-%d')}.csv"
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/actions/{action_id}", response_class=HTMLResponse)
async def view_action(request: Request, action_id: int):
    """View details of a specific action."""
    with get_session() as session:
        action = session.query(Action).filter_by(id=action_id).first()

        if not action:
            raise HTTPException(status_code=404, detail="Action not found")

        # Get assignment if exists
        assignment = session.query(Assignment).filter_by(action_id=action_id).first()

        # Get other actions from the same email
        related_actions = session.query(Action).filter(
            Action.email_id == action.email_id,
            Action.id != action_id
        ).all()

        # Get roster for assignment dropdown
        roster = get_active_roster(session)

        # Get recent assignees as fallback when no roster
        # Use subquery to avoid PG error: DISTINCT + ORDER BY on different columns
        recent_sub = session.query(
            Assignment.assigned_to,
            func.max(Assignment.assigned_at).label("last_assigned"),
        ).group_by(Assignment.assigned_to).subquery()
        recent_assignees = session.query(recent_sub.c.assigned_to).order_by(
            desc(recent_sub.c.last_assigned)
        ).limit(10).all()
        recent_assignee_list = [a[0] for a in recent_assignees if a[0]]

        ai_config = SettingsService.get_ai_config()
        categories = ai_config.get('categories', SettingsService.DEFAULT_CATEGORIES)

        # Search KB for program context related to this action
        kb_matches = search_knowledge_base(
            sender=action.email.from_address,
            title=action.title,
            description=action.description or "",
            category=action.category or "",
        )

        return templates.TemplateResponse("action_detail.html", {
            "request": request,
            "action": action,
            "assignment": assignment,
            "related_actions": related_actions,
            "roster": roster,
            "recent_assignees": recent_assignee_list,
            "current_time": utcnow(),
            "categories": categories,
            "kb_matches": kb_matches,
        })


@router.post("/actions/{action_id}/assign")
async def assign_action(
    request: Request,
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
            existing.assigned_at = utcnow()
        else:
            # Create new assignment
            assignment = Assignment(
                action_id=action_id,
                assigned_to=assigned_to,
                notes=notes,
                status="assigned"
            )
            session.add(assignment)

        log_audit(session, request, "assign", "action", action_id,
                  {"assigned_to": assigned_to})
        session.commit()

    return RedirectResponse(url=f"/actions/{action_id}", status_code=303)


@router.post("/actions/{action_id}/complete")
async def complete_action(request: Request, action_id: int):
    """Mark an action as completed."""
    with get_session() as session:
        assignment = session.query(Assignment).filter_by(action_id=action_id).first()

        if not assignment:
            # Create assignment with completed status
            assignment = Assignment(
                action_id=action_id,
                assigned_to="Unknown",
                status="completed",
                completed_at=utcnow()
            )
            session.add(assignment)
        else:
            assignment.status = "completed"
            assignment.completed_at = utcnow()

        log_audit(session, request, "complete", "action", action_id)
        session.commit()

    return RedirectResponse(url=f"/actions/{action_id}", status_code=303)


@router.post("/actions/{action_id}/priority")
async def change_priority(request: Request, action_id: int, priority: str = Form(...)):
    """Quick-change priority (used by dashboard AJAX)."""
    with get_session() as session:
        action = session.query(Action).filter_by(id=action_id).first()
        if not action:
            raise HTTPException(status_code=404, detail="Action not found")
        if priority in ["high", "medium", "low"]:
            old_priority = action.priority
            action.priority = priority
            log_audit(session, request, "change_priority", "action", action_id,
                      {"old": old_priority, "new": priority})
            session.commit()
    return RedirectResponse(url=f"/actions/{action_id}", status_code=303)


@router.post("/actions/{action_id}/unassign")
async def unassign_action(request: Request, action_id: int):
    """Remove assignment from an action (used by dashboard AJAX)."""
    with get_session() as session:
        assignment = session.query(Assignment).filter_by(action_id=action_id).first()
        if assignment:
            log_audit(session, request, "unassign", "action", action_id,
                      {"was_assigned_to": assignment.assigned_to})
            session.delete(assignment)
            session.commit()
    return RedirectResponse(url=f"/actions/{action_id}", status_code=303)


@router.post("/actions/{action_id}/status")
async def update_assignment_status(
    request: Request,
    action_id: int,
    status: str = Form(...)
):
    """Update assignment status (assigned, completed)."""
    with get_session() as session:
        assignment = session.query(Assignment).filter_by(action_id=action_id).first()

        if not assignment:
            raise HTTPException(status_code=404, detail="Action not assigned")

        if status not in ["assigned", "in_progress", "completed"]:
            raise HTTPException(status_code=400, detail="Invalid status")

        old_status = assignment.status
        assignment.status = status
        if status == "completed":
            assignment.completed_at = utcnow()
        else:
            assignment.completed_at = None
        log_audit(session, request, "update", "assignment", action_id,
                  {"old_status": old_status, "new_status": status})
        session.commit()

    return RedirectResponse(url=f"/actions/{action_id}", status_code=303)


@router.post("/actions/{action_id}/edit")
async def edit_action(
    request: Request,
    action_id: int,
    title: str = Form(...),
    description: str = Form(""),
    priority: str = Form("medium"),
    due_date: str = Form(""),
    category: str = Form(""),
    assigned_to: str = Form(""),
    notes: str = Form(""),
):
    """Update action fields and optionally assign in one submit."""
    with get_session() as session:
        action = session.query(Action).filter_by(id=action_id).first()
        if not action:
            raise HTTPException(status_code=404, detail="Action not found")

        # Block edits on completed actions — must reopen first
        existing_assignment = session.query(Assignment).filter_by(action_id=action_id).first()
        if existing_assignment and existing_assignment.status == "completed":
            return RedirectResponse(url=f"/actions/{action_id}", status_code=303)

        action.title = title.strip()
        action.description = description.strip() if description.strip() else None
        action.category = category.strip() if category.strip() else None

        if priority in ["high", "medium", "low"]:
            action.priority = priority

        if due_date and due_date.strip():
            from datetime import datetime as dt
            try:
                action.due_date = dt.strptime(due_date.strip(), "%Y-%m-%d").date()
            except ValueError:
                pass
        else:
            action.due_date = None

        # Handle assignment
        existing = session.query(Assignment).filter_by(action_id=action_id).first()
        if assigned_to and assigned_to.strip():
            if existing:
                existing.assigned_to = assigned_to.strip()
                existing.notes = notes.strip() if notes.strip() else existing.notes
                existing.assigned_at = utcnow()
            else:
                new_assignment = Assignment(
                    action_id=action_id,
                    assigned_to=assigned_to.strip(),
                    notes=notes.strip() if notes.strip() else None,
                    status="assigned",
                )
                session.add(new_assignment)
        elif existing:
            # User selected "Unassigned" — remove the assignment
            session.delete(existing)

        log_audit(session, request, "update", "action", action_id)
        session.commit()

    return RedirectResponse(url=f"/actions/{action_id}", status_code=303)


@router.post("/actions/{action_id}/delete")
async def delete_action(request: Request, action_id: int):
    """Delete an action."""
    with get_session() as session:
        action = session.query(Action).filter_by(id=action_id).first()
        if not action:
            raise HTTPException(status_code=404, detail="Action not found")

        email_id = action.email_id
        log_audit(session, request, "delete", "action", action_id,
                  {"title": action.title})
        session.delete(action)
        session.commit()

    return RedirectResponse(url=f"/emails/{email_id}", status_code=303)


@router.get("/emails/{email_id}/actions/new", response_class=HTMLResponse)
async def new_action_form(request: Request, email_id: int):
    """Show form to create a new action for an email."""
    with get_session() as session:
        email = session.query(Email).filter_by(id=email_id).first()
        if not email:
            raise HTTPException(status_code=404, detail="Email not found")

        ai_config = SettingsService.get_ai_config()
        categories = ai_config.get('categories', SettingsService.DEFAULT_CATEGORIES)
        return templates.TemplateResponse("action_new.html", {
            "request": request,
            "email": email,
            "categories": categories,
        })


@router.post("/emails/{email_id}/actions/new")
async def create_action(
    request: Request,
    email_id: int,
    title: str = Form(...),
    description: str = Form(""),
    priority: str = Form("medium"),
    due_date: Optional[str] = Form(None),
    category: str = Form("")
):
    """Create a new action for an email."""
    with get_session() as session:
        email = session.query(Email).filter_by(id=email_id).first()
        if not email:
            raise HTTPException(status_code=404, detail="Email not found")

        # Parse due date if provided
        parsed_due_date = None
        if due_date and due_date.strip():
            try:
                from datetime import datetime as dt
                parsed_due_date = dt.strptime(due_date, '%Y-%m-%d')
            except ValueError:
                pass

        # Create new action
        action = Action(
            email_id=email_id,
            title=title,
            description=description if description.strip() else None,
            priority=priority,
            due_date=parsed_due_date,
            category=category if category.strip() else None,
            confidence_score=1.0  # Manual actions are 100% confident
        )

        session.add(action)
        session.flush()
        log_audit(session, request, "create", "action", action.id,
                  {"title": title, "priority": priority, "email_id": email_id})
        session.commit()
        session.refresh(action)
        action_id = action.id  # capture before session closes

    return RedirectResponse(url=f"/actions/{action_id}", status_code=303)
