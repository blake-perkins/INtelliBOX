"""Analytics dashboard route."""

from datetime import timedelta

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import case, desc, func

from intellibox.models import Action, Assignment, Email, RosterMember
from intellibox.utils.datetime_utils import utcnow
from intellibox.web.deps import get_session, templates

router = APIRouter()


@router.get("/analytics", response_class=HTMLResponse)
async def view_analytics(request: Request):
    """System analytics dashboard — all-time stats and activity trends."""
    with get_session() as session:
        now = utcnow()
        today = now.date()

        # --- All-time counters ---
        total_emails = session.query(Email).count()
        total_actions = session.query(Action).count()
        total_completed = session.query(Assignment).filter(
            Assignment.status == "completed"
        ).count()
        total_members = session.query(RosterMember).count()

        # --- Current pipeline ---
        unassigned = session.query(Action).outerjoin(Assignment).filter(
            Assignment.id.is_(None)
        ).count()
        in_progress = session.query(Assignment).filter(
            Assignment.status != "completed"
        ).count()
        overdue = session.query(Action).outerjoin(Assignment).filter(
            Action.due_date < today,
            (Assignment.id.is_(None)) | (Assignment.status != "completed")
        ).count()

        # --- Weekly activity (last 4 weeks) ---
        weeks = []
        for i in range(4):
            week_end = now - timedelta(days=i * 7)
            week_start = week_end - timedelta(days=7)
            emails_count = session.query(Email).filter(
                Email.created_at >= week_start,
                Email.created_at < week_end
            ).count()
            actions_count = session.query(Action).filter(
                Action.created_at >= week_start,
                Action.created_at < week_end
            ).count()
            completed_count = session.query(Assignment).filter(
                Assignment.status == "completed",
                Assignment.completed_at >= week_start,
                Assignment.completed_at < week_end
            ).count()
            weeks.append({
                "label": week_start.strftime("%b %d") + " – " + (week_end - timedelta(days=1)).strftime("%b %d"),
                "emails": emails_count,
                "actions": actions_count,
                "completed": completed_count,
            })
        weeks.reverse()  # oldest first

        # --- Top categories (top 5) ---
        category_rows = session.query(
            Action.category, func.count(Action.id).label("cnt")
        ).filter(Action.category.isnot(None), Action.category != "").group_by(
            Action.category
        ).order_by(desc("cnt")).limit(5).all()
        top_categories = [{"name": r[0], "count": r[1]} for r in category_rows]

        # --- Team activity ---
        team_rows = session.query(
            Assignment.assigned_to,
            func.count(case((Assignment.status == "completed", 1))).label("done"),
            func.count(case((Assignment.status != "completed", 1))).label("active"),
        ).group_by(Assignment.assigned_to).order_by(desc("done")).all()
        team_activity = [{"name": r[0], "completed": r[1], "active": r[2]} for r in team_rows]

        # Max values for bar scaling
        max_weekly = max(
            (max(w["emails"], w["actions"], w["completed"]) for w in weeks),
            default=0
        )

        return templates.TemplateResponse("analytics.html", {
            "request": request,
            "total_emails": total_emails,
            "total_actions": total_actions,
            "total_completed": total_completed,
            "total_members": total_members,
            "unassigned": unassigned,
            "in_progress": in_progress,
            "completed_all": total_completed,
            "overdue": overdue,
            "weeks": weeks,
            "max_weekly": max_weekly,
            "top_categories": top_categories,
            "team_activity": team_activity,
        })
