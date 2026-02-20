"""Dashboard route."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import case, desc, func
from sqlalchemy.orm import joinedload

from intellibox.models import Action, Assignment, Email, RosterMember
from intellibox.utils.datetime_utils import utcnow
from intellibox.web.deps import get_session, templates
from intellibox.web.queries import format_time_ago

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard showing summary statistics."""
    with get_session() as session:
        # Get statistics — single aggregated query
        total_emails = session.query(func.count(Email.id)).scalar()
        stats = session.query(
            func.count(Action.id).label("total_actions"),
            func.count(case((Assignment.id.is_(None), Action.id))).label("unassigned"),
            func.count(case(((Assignment.id.is_(None)) & (Action.priority == "high"), Action.id))).label("high"),
            func.count(case(((Assignment.id.is_(None)) & (Action.priority == "medium"), Action.id))).label("medium"),
            func.count(case(((Assignment.id.is_(None)) & (Action.priority == "low"), Action.id))).label("low"),
            func.count(case((Assignment.id.isnot(None), Action.id))).label("assigned"),
            func.count(case((Assignment.status == "completed", Action.id))).label("completed"),
        ).select_from(Action).outerjoin(Assignment).one()

        total_actions = stats.total_actions
        unassigned_actions = stats.unassigned
        high_priority = stats.high
        medium_priority = stats.medium
        low_priority = stats.low
        assigned_actions = stats.assigned
        completed_actions = stats.completed

        # Get overdue actions (assigned or unassigned, exclude completed)
        today = utcnow().date()
        overdue_count = session.query(Action).outerjoin(Assignment).filter(
            Action.due_date < today,
            (Assignment.id.is_(None)) | (Assignment.status != "completed")
        ).count()
        overdue_actions = session.query(Action).options(
            joinedload(Action.assignments), joinedload(Action.email),
        ).outerjoin(Assignment).join(Email).filter(
            Action.due_date < today,
            (Assignment.id.is_(None)) | (Assignment.status != "completed")
        ).order_by(Action.due_date).all()

        # Get high priority unassigned actions
        high_priority_actions = session.query(Action).options(
            joinedload(Action.assignments), joinedload(Action.email),
        ).outerjoin(Assignment).join(Email).filter(
            Assignment.id.is_(None),
            Action.priority == "high"
        ).order_by(Action.due_date.asc().nullslast()).all()

        # Get medium and low priority unassigned actions
        medium_priority_actions = session.query(Action).options(
            joinedload(Action.assignments), joinedload(Action.email),
        ).outerjoin(Assignment).join(Email).filter(
            Assignment.id.is_(None),
            Action.priority == "medium"
        ).order_by(Action.due_date.asc().nullslast()).all()

        low_priority_actions = session.query(Action).options(
            joinedload(Action.assignments), joinedload(Action.email),
        ).outerjoin(Assignment).join(Email).filter(
            Assignment.id.is_(None),
            Action.priority == "low"
        ).order_by(Action.due_date.asc().nullslast()).all()

        # Get recent assignments (last 5, exclude completed)
        recent_assignments = session.query(Assignment, Action).join(
            Action
        ).filter(
            Assignment.status == "assigned"
        ).order_by(desc(Assignment.assigned_at)).limit(5).all()

        # Get recently completed (last 5)
        recent_completions = session.query(Assignment, Action).join(
            Action
        ).filter(
            Assignment.status == "completed"
        ).order_by(desc(Assignment.assigned_at)).limit(5).all()

        # Get roster for quick-assign dropdowns
        roster = session.query(RosterMember).filter_by(active=True).order_by(
            RosterMember.last_name, RosterMember.first_name
        ).all()

        # Get latest email date for "last updated" info
        latest_email = session.query(Email).order_by(desc(Email.received_date)).first()
        last_email_date = latest_email.received_date if latest_email else None
        time_since_last_email = format_time_ago(last_email_date)

        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "total_emails": total_emails,
            "total_actions": total_actions,
            "unassigned_actions": unassigned_actions,
            "assigned_actions": assigned_actions,
            "completed_actions": completed_actions,
            "high_priority": high_priority,
            "medium_priority": medium_priority,
            "low_priority": low_priority,
            "overdue_count": overdue_count,
            "overdue_actions": overdue_actions,
            "high_priority_actions": high_priority_actions,
            "medium_priority_actions": medium_priority_actions,
            "low_priority_actions": low_priority_actions,
            "roster": roster,
            "recent_assignments": recent_assignments,
            "recent_completions": recent_completions,
            "last_email_date": last_email_date,
            "time_since_last_email": time_since_last_email,
            "current_time": utcnow(),
        })
