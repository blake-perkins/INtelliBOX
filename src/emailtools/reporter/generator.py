"""Report generation for daily email summaries."""

from datetime import datetime, timedelta
from typing import Dict, List

from sqlalchemy import and_
from sqlalchemy.orm import Session

from emailtools.ai.processor import get_ai_client
from emailtools.config import settings
from emailtools.models import Action, Email
from emailtools.utils.logging import logger


def get_unassigned_actions(session: Session) -> List[Action]:
    """
    Get all unassigned actions sorted by priority and due date.

    Args:
        session: Database session

    Returns:
        List of unassigned Action objects
    """
    # Query actions that have no assignments
    query = (
        session.query(Action)
        .outerjoin(Action.assignments)
        .filter(Action.assignments == None)
        .order_by(
            # Sort by priority (high first), then due date (earliest first)
            Action.priority.desc(),
            Action.due_date.asc()
        )
    )

    actions = query.all()
    logger.info(f"Found {len(actions)} unassigned action(s)")
    return actions


def get_recent_emails(session: Session, days: int = 7) -> List[Email]:
    """
    Get emails from the past N days.

    Args:
        session: Database session
        days: Number of days to look back

    Returns:
        List of Email objects
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    emails = (
        session.query(Email)
        .filter(Email.received_date >= cutoff_date)
        .order_by(Email.received_date.desc())
        .all()
    )

    logger.info(f"Found {len(emails)} email(s) from past {days} days")
    return emails


def generate_program_news(session: Session, days: int = None) -> str:
    """
    Generate program news summary using AI.

    Args:
        session: Database session
        days: Number of days to summarize (default from config)

    Returns:
        Program news summary text
    """
    if days is None:
        days = settings.program_news_days

    recent_emails = get_recent_emails(session, days)

    if not recent_emails:
        return "No email activity in the past {} days.".format(days)

    # Use AI client to generate summary
    client = get_ai_client()

    try:
        summary = client.generate_program_news(recent_emails, days)
        logger.info("Program news summary generated")
        return summary
    except Exception as e:
        logger.error(f"Failed to generate program news: {e}")
        return f"Unable to generate program news summary. ({len(recent_emails)} emails received in past {days} days)"


def generate_report_data(session: Session) -> Dict:
    """
    Generate all data needed for the daily report.

    Args:
        session: Database session

    Returns:
        Dictionary with report data
    """
    logger.info("Generating daily report data")

    # Get unassigned actions
    unassigned_actions = get_unassigned_actions(session)

    # Get program news
    program_news = generate_program_news(session)

    # Calculate statistics
    high_priority_count = sum(1 for a in unassigned_actions if a.priority == "high")
    medium_priority_count = sum(1 for a in unassigned_actions if a.priority == "medium")
    low_priority_count = sum(1 for a in unassigned_actions if a.priority == "low")

    # Get count of emails processed today
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    emails_today = (
        session.query(Email)
        .filter(Email.created_at >= today_start)
        .count()
    )

    report_data = {
        "generated_at": datetime.utcnow(),
        "unassigned_actions": unassigned_actions,
        "total_actions": len(unassigned_actions),
        "high_priority_count": high_priority_count,
        "medium_priority_count": medium_priority_count,
        "low_priority_count": low_priority_count,
        "program_news": program_news,
        "emails_today": emails_today,
    }

    logger.info(
        f"Report generated: {len(unassigned_actions)} unassigned actions "
        f"({high_priority_count} high, {medium_priority_count} medium, {low_priority_count} low)"
    )

    return report_data
