"""Shared query helpers used by multiple routers."""

from datetime import datetime
from typing import Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from intellibox.models import Action, Assignment, Email, RosterMember
from intellibox.utils.datetime_utils import utcnow


def get_banner_stats(session: Session) -> dict:
    """Compute stats shown in the banner across multiple pages."""
    today = utcnow().date()
    unassigned_actions = (
        session.query(Action).outerjoin(Assignment).filter(Assignment.id.is_(None)).count()
    )
    high_priority = (
        session.query(Action)
        .outerjoin(Assignment)
        .filter(Action.priority == "high", Assignment.id.is_(None))
        .count()
    )
    overdue_count = (
        session.query(Action)
        .outerjoin(Assignment)
        .filter(
            Action.due_date < today,
            (Assignment.id.is_(None)) | (Assignment.status != "completed"),
        )
        .count()
    )
    return {
        "unassigned_actions": unassigned_actions,
        "high_priority": high_priority,
        "overdue_count": overdue_count,
    }


def format_time_ago(dt: Optional[datetime]) -> Optional[str]:
    """Format a datetime as a human-readable relative string like '2m ago'."""
    if dt is None:
        return None
    delta = utcnow() - dt
    if delta.total_seconds() < 3600:
        return f"{int(delta.total_seconds() / 60)}m ago"
    elif delta.total_seconds() < 86400:
        return f"{int(delta.total_seconds() / 3600)}h ago"
    else:
        return f"{int(delta.total_seconds() / 86400)}d ago"


def get_time_since_last_email(session: Session) -> Optional[str]:
    """Return human-readable time since the most recent email."""
    latest = session.query(Email).order_by(desc(Email.received_date)).first()
    if latest:
        return format_time_ago(latest.received_date)
    return None


def get_active_roster(session: Session) -> list:
    """Return active roster members sorted by last name, first name."""
    return (
        session.query(RosterMember)
        .filter_by(active=True)
        .order_by(RosterMember.last_name, RosterMember.first_name)
        .all()
    )


def paginate(query, page: int, per_page: int = 50) -> tuple:
    """Apply pagination to a query. Returns (items, total_count, total_pages)."""
    total_count = query.count()
    total_pages = (total_count + per_page - 1) // per_page
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return items, total_count, total_pages
