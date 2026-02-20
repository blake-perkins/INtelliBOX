"""API, health, and about routes."""

from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import case, func

from intellibox import __version__
from intellibox.models import Action, Assignment, Email
from intellibox.settings_service import SettingsService
from intellibox.utils.datetime_utils import utcnow
from intellibox.web.deps import get_session, templates

router = APIRouter()


@router.get("/api/stats")
async def get_stats():
    """API endpoint for statistics (for auto-refresh)."""
    with get_session() as session:
        today = utcnow().date()
        last_sync = "never"
        last_sync_str = SettingsService.get_setting('last_sync_time', None)
        if last_sync_str:
            try:
                last_sync_dt = datetime.fromisoformat(last_sync_str)
                delta = utcnow() - last_sync_dt
                if delta.total_seconds() < 3600:
                    last_sync = f"{int(delta.total_seconds() / 60)}m ago"
                elif delta.total_seconds() < 86400:
                    last_sync = f"{int(delta.total_seconds() / 3600)}h ago"
                else:
                    last_sync = f"{int(delta.total_seconds() / 86400)}d ago"
            except (ValueError, TypeError):
                pass
        # Single aggregated query for all action/assignment stats
        s = session.query(
            func.count(Action.id).label("total_actions"),
            func.count(case((Assignment.id.is_(None), Action.id))).label("unassigned"),
            func.count(case(((Assignment.id.is_(None)) & (Action.priority == "high"), Action.id))).label("unassigned_high"),
            func.count(case(((Assignment.id.is_(None)) & (Action.priority == "medium"), Action.id))).label("unassigned_medium"),
            func.count(case(((Assignment.id.is_(None)) & (Action.priority == "low"), Action.id))).label("unassigned_low"),
            func.count(case((
                (Action.due_date < today) & ((Assignment.id.is_(None)) | (Assignment.status != "completed")), Action.id
            ))).label("overdue"),
            func.count(case(((Assignment.id.isnot(None)) & (Assignment.status != "completed"), Action.id))).label("assigned"),
            func.count(case((
                (Assignment.status != "completed") & (Action.priority == "high") & (Assignment.id.isnot(None)), Action.id
            ))).label("assigned_high"),
            func.count(case((
                (Assignment.status != "completed") & (Action.priority == "medium") & (Assignment.id.isnot(None)), Action.id
            ))).label("assigned_medium"),
            func.count(case((
                (Assignment.status != "completed") & (Action.priority == "low") & (Assignment.id.isnot(None)), Action.id
            ))).label("assigned_low"),
            func.count(case((Assignment.status == "completed", Action.id))).label("completed"),
        ).select_from(Action).outerjoin(Assignment).one()

        total_emails = session.query(func.count(Email.id)).scalar()

        return {
            "last_sync": last_sync,
            "total_emails": total_emails,
            "total_actions": s.total_actions,
            "unassigned_actions": s.unassigned,
            "unassigned_high": s.unassigned_high,
            "unassigned_medium": s.unassigned_medium,
            "unassigned_low": s.unassigned_low,
            "overdue_count": s.overdue,
            "assigned_actions": s.assigned,
            "assigned_high": s.assigned_high,
            "assigned_medium": s.assigned_medium,
            "assigned_low": s.assigned_low,
            "completed_actions": s.completed,
        }


@router.get("/health")
async def health_check():
    """Health check endpoint with watcher status."""
    from intellibox.ingestion.file_watcher import get_watcher_health

    return {
        "status": "healthy",
        "version": __version__,
        "timestamp": utcnow().isoformat(),
        "watcher": get_watcher_health(),
    }


@router.get("/about", response_class=HTMLResponse)
async def about_page(request: Request):
    """About page describing the product."""
    return templates.TemplateResponse("about.html", {"request": request})
