"""Report generation for daily email summaries."""

import json
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from typing import Dict, List
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from emailtools.ai.processor import get_ai_client
from emailtools.config import settings
from emailtools.models import Action, Assignment, Email, ProgramNewsCache, ReportCache
from emailtools.utils.datetime_utils import utcnow
from emailtools.utils.logging import logger


def to_local_time(dt: datetime, tz_name: str) -> datetime:
    """Convert a naive UTC datetime to the given IANA timezone."""
    if dt is None:
        return dt
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        logger.warning(f"Unknown timezone '{tz_name}', falling back to UTC")
        tz = dt_timezone.utc
    return dt.replace(tzinfo=dt_timezone.utc).astimezone(tz)


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
    cutoff_date = utcnow() - timedelta(days=days)

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


def get_cached_program_news(session: Session, days: int = None, force_refresh: bool = False) -> Dict:
    """
    Get cached program news or generate new if needed.

    Cache is refreshed when:
    - force_refresh is True
    - No cache exists
    - Cache is older than 12 hours
    - New emails received since last generation

    Args:
        session: Database session
        days: Number of days to summarize (default from config)
        force_refresh: Force regeneration even if cache is valid

    Returns:
        Dict with 'summary', 'generated_at', and 'is_cached' fields
    """
    if days is None:
        days = settings.program_news_days

    # Get most recent cache entry
    latest_cache = session.query(ProgramNewsCache).filter(
        ProgramNewsCache.days_covered == days
    ).order_by(ProgramNewsCache.generated_at.desc()).first()

    # Check if we need to regenerate
    should_regenerate = force_refresh

    if not should_regenerate and latest_cache:
        # Check if cache is older than 12 hours
        cache_age = utcnow() - latest_cache.generated_at
        if cache_age.total_seconds() > (12 * 3600):
            should_regenerate = True
            logger.info(f"Cache is {cache_age.total_seconds() / 3600:.1f} hours old, regenerating")

        # Check if new emails have been received since cache was generated
        if not should_regenerate and latest_cache.latest_email_date:
            newest_email = session.query(Email).order_by(Email.received_date.desc()).first()
            if newest_email and newest_email.received_date > latest_cache.latest_email_date:
                should_regenerate = True
                logger.info("New emails received since last cache, regenerating")
    elif not latest_cache:
        should_regenerate = True
        logger.info("No cache found, generating program news")

    # Use cache if valid
    if not should_regenerate and latest_cache:
        logger.info(f"Using cached program news (generated {latest_cache.generated_at})")
        return {
            "summary": latest_cache.summary,
            "generated_at": latest_cache.generated_at,
            "is_cached": True,
            "email_count": latest_cache.email_count
        }

    # Generate new summary
    recent_emails = get_recent_emails(session, days)
    summary = generate_program_news(session, days)

    # Get latest email date
    latest_email_date = None
    if recent_emails:
        latest_email_date = max(email.received_date for email in recent_emails)

    # Save to cache
    cache_entry = ProgramNewsCache(
        summary=summary,
        days_covered=days,
        email_count=len(recent_emails),
        latest_email_date=latest_email_date,
        generated_at=utcnow()
    )
    session.add(cache_entry)
    session.commit()

    # Prune old cache entries
    from emailtools.database import cleanup_cache_tables
    cleanup_cache_tables(session, keep_program_news=5, keep_report=0)
    session.commit()

    logger.info(f"Program news cached ({len(recent_emails)} emails)")

    return {
        "summary": summary,
        "generated_at": cache_entry.generated_at,
        "is_cached": False,
        "email_count": len(recent_emails)
    }


def get_cached_structured_program_news(session: Session, days: int = None, force_refresh: bool = False) -> Dict:
    """
    Get cached structured program news or generate new if explicitly requested.

    Only regenerates when force_refresh=True. Normal page loads always return
    cached data instantly (even if stale) to avoid blocking on AI calls.

    Args:
        session: Database session
        days: Number of days to summarize (default from config)
        force_refresh: Force regeneration even if cache is valid

    Returns:
        Dict with structured news data, generated_at, is_cached, and email_count fields
    """
    if days is None:
        days = settings.program_news_days

    # Get most recent cache entry
    latest_cache = session.query(ProgramNewsCache).filter(
        ProgramNewsCache.days_covered == days
    ).order_by(ProgramNewsCache.generated_at.desc()).first()

    # Only regenerate when explicitly requested — never auto-regen on page load
    should_regenerate = force_refresh

    if not latest_cache and not force_refresh:
        logger.info("No structured news cache found; waiting for user to trigger generation")
        return {
            "structured_data": None,
            "generated_at": None,
            "is_cached": False,
            "email_count": 0
        }

    # Use cache if valid
    if not should_regenerate and latest_cache:
        logger.info(f"Using cached structured program news (generated {latest_cache.generated_at})")
        # Try to parse the summary as JSON (new format)
        try:
            structured_data = json.loads(latest_cache.summary)
            return {
                "structured_data": structured_data,
                "generated_at": latest_cache.generated_at,
                "is_cached": True,
                "email_count": latest_cache.email_count
            }
        except json.JSONDecodeError:
            # Old format, regenerate
            logger.info("Cache is in old format, regenerating")
            should_regenerate = True

    # Generate new structured summary
    recent_emails = get_recent_emails(session, days)

    client = get_ai_client()
    try:
        structured_data = client.generate_structured_program_news(recent_emails, days)
    except Exception as e:
        logger.error(f"Failed to generate structured program news: {e}")
        structured_data = {
            "critical_updates": [],
            "trending_topics": [],
            "volume_summary": {
                "total_emails": len(recent_emails),
                "trend_description": "Error generating summary",
                "notable_pattern": ""
            },
            "top_senders": [],
            "key_takeaways": ["Error generating program news"]
        }

    # Get latest email date
    latest_email_date = None
    if recent_emails:
        latest_email_date = max(email.received_date for email in recent_emails)

    # Save to cache as JSON
    cache_entry = ProgramNewsCache(
        summary=json.dumps(structured_data),  # Store as JSON
        days_covered=days,
        email_count=len(recent_emails),
        latest_email_date=latest_email_date,
        generated_at=utcnow()
    )
    session.add(cache_entry)
    session.commit()

    from emailtools.database import cleanup_cache_tables
    cleanup_cache_tables(session, keep_program_news=5, keep_report=0)
    session.commit()

    logger.info(f"Structured program news cached ({len(recent_emails)} emails)")

    return {
        "structured_data": structured_data,
        "generated_at": cache_entry.generated_at,
        "is_cached": False,
        "email_count": len(recent_emails)
    }


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
    today_start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    emails_today = (
        session.query(Email)
        .filter(Email.created_at >= today_start)
        .count()
    )

    from emailtools.settings_service import SettingsService
    tz_name = SettingsService.get_timezone()

    report_data = {
        "generated_at": to_local_time(utcnow(), tz_name),
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


def generate_enhanced_report(session: Session, days: int = 7, force_refresh: bool = False) -> Dict:
    """
    Generate enhanced report with AI insights and caching.

    Cache is refreshed when:
    - force_refresh is True
    - No cache exists
    - Cache is older than 1 hour
    - New actions have been created since last generation

    Args:
        session: Database session
        days: Number of days to analyze for insights
        force_refresh: Force regeneration even if cache is valid

    Returns:
        Dictionary with comprehensive report data and insights
    """
    # Always get fresh action data (cheap query)
    unassigned_actions = get_unassigned_actions(session)

    # Calculate basic statistics
    now = utcnow()
    today = now.date()
    high_priority_count = sum(1 for a in unassigned_actions if a.priority == "high")
    medium_priority_count = sum(1 for a in unassigned_actions if a.priority == "medium")
    low_priority_count = sum(1 for a in unassigned_actions if a.priority == "low")

    # Overdue and due this week — across ALL non-completed actions (not just unassigned)
    # This matches the /api/stats logic so numbers are consistent across the app
    week_from_now = now + timedelta(days=7)
    overdue_count = session.query(Action).outerjoin(Assignment).filter(
        Action.due_date < today,
        (Assignment.id.is_(None)) | (Assignment.status != "completed")
    ).count()
    due_this_week_count = session.query(Action).outerjoin(Assignment).filter(
        Action.due_date >= today,
        Action.due_date <= week_from_now,
        (Assignment.id.is_(None)) | (Assignment.status != "completed")
    ).count()

    # Pipeline counts — always fresh (cheap queries)
    assigned_in_progress = session.query(Assignment).filter(
        Assignment.status != "completed"
    ).count()
    completed_count = session.query(Assignment).filter(
        Assignment.status == "completed"
    ).count()

    # Completed this week (assignments marked complete in the last 7 days)
    week_ago = now - timedelta(days=7)
    completed_this_week = session.query(Assignment).filter(
        Assignment.status == "completed",
        Assignment.completed_at >= week_ago
    ).count()

    # Check cache for AI insights (expensive operation)
    latest_cache = session.query(ReportCache).order_by(
        ReportCache.generated_at.desc()
    ).first()

    # Only regenerate when explicitly requested (force_refresh). Never
    # auto-regenerate on normal page loads — that blocks the request on a
    # slow AI call. When no cache exists the template shows a "Generate" CTA.
    should_regenerate_insights = force_refresh

    if not latest_cache and not force_refresh:
        logger.info("No insights cache found; waiting for user to trigger generation")

    # Get or generate AI insights
    if not should_regenerate_insights and not latest_cache:
        # No cache and user hasn't requested generation — show empty state
        insights = None
        is_cached = False
        insights_generated_at = None
    elif not should_regenerate_insights and latest_cache:
        logger.info(f"Using cached AI insights (generated {latest_cache.generated_at})")
        cached_data = json.loads(latest_cache.report_data)
        insights = cached_data.get("insights", {})
        is_cached = True
        insights_generated_at = latest_cache.generated_at
    else:
        # Generate new KB-aware AI insights
        logger.info("Generating new AI insights")
        recent_emails = get_recent_emails(session, days)

        # Gather active actions (unassigned + in-progress) plus recently
        # completed ones.  This keeps the analysis focused on current work
        # while still showing recent throughput.
        cutoff = now - timedelta(days=days)
        all_actions = (
            session.query(Action)
            .outerjoin(Assignment)
            .filter(
                # Active: no assignment or assignment not completed
                (Assignment.id.is_(None)) | (Assignment.status != "completed")
                # OR completed within the lookback window
                | (Assignment.completed_at >= cutoff)
            )
            .distinct()
            .all()
        )

        # Format action details for the AI prompt
        action_lines = []
        for i, action in enumerate(all_actions, 1):
            # Determine status
            if action.assignments:
                statuses = []
                for asn in action.assignments:
                    if asn.status == "completed":
                        statuses.append(f"COMPLETED ({asn.assigned_to})")
                    else:
                        statuses.append(f"IN PROGRESS ({asn.assigned_to})")
                status = ", ".join(statuses)
            else:
                status = "UNASSIGNED"

            pri = (action.priority or "medium").upper()
            cat = f", {action.category}" if action.category else ""
            due = f", due: {action.due_date.strftime('%Y-%m-%d')}" if action.due_date else ""
            line = f'{i}. [{pri}] "{action.title}"{cat}{due} -- {status}'
            if action.description:
                line += f"\n   {action.description[:200]}"
            action_lines.append(line)
        action_details_text = "\n".join(action_lines) if action_lines else "No actions in pipeline"

        # Format email summaries
        email_summary_lines = []
        for email in recent_emails[:20]:
            email_summary_lines.append(f"- From {email.from_address}: {email.subject}")
        email_summaries_text = "\n".join(email_summary_lines) if email_summary_lines else "No recent emails"

        # Compute pipeline stats
        total_overdue = session.query(Action).outerjoin(Assignment).filter(
            Action.due_date < now,
            (Assignment.id.is_(None)) | (Assignment.status != "completed")
        ).count()

        pipeline_stats = {
            "total_actions": len(all_actions),
            "unassigned": len(unassigned_actions),
            "high": high_priority_count,
            "medium": medium_priority_count,
            "low": low_priority_count,
            "assigned_in_progress": assigned_in_progress,
            "completed": completed_count,
            "overdue": total_overdue,
            "due_this_week": due_this_week_count,
        }

        client = get_ai_client()
        try:
            insights = client.generate_report_insights(
                action_details_text, email_summaries_text, days,
                pipeline_stats=pipeline_stats
            )
        except Exception as e:
            logger.error(f"Failed to generate AI insights: {e}")
            insights = {
                "executive_summary": {
                    "headline": "Unable to generate insights at this time",
                    "key_finding": "",
                    "top_risk": "",
                    "recommended_action": ""
                },
                "sow_alignment": {"mapped_deliverables": [], "unmapped_actions": [], "coverage_gaps": []},
                "risk_radar": [],
                "process_compliance": {"observations": [], "overall_health": "green"},
                "trend_intelligence": {"patterns": [], "workload_forecast": ""},
                "recommendations": []
            }

        # Save insights to cache
        cache_data = {
            "insights": insights,
            "email_count": len(recent_emails) if 'recent_emails' in locals() else 0
        }

        cache_entry = ReportCache(
            report_data=json.dumps(cache_data),
            generated_at=now
        )
        session.add(cache_entry)
        session.commit()

        from emailtools.database import cleanup_cache_tables
        cleanup_cache_tables(session, keep_program_news=0, keep_report=5)
        session.commit()

        logger.info("AI insights cached")
        is_cached = False
        insights_generated_at = now

    # Insights are considered stale if cached and older than 1 hour, or if new
    # actions exist since the cache was generated.
    is_stale = False
    if is_cached and insights_generated_at:
        cache_age_seconds = (now - insights_generated_at).total_seconds()
        if cache_age_seconds > 3600:
            is_stale = True
        else:
            newest_action = session.query(Action).order_by(Action.created_at.desc()).first()
            if newest_action and newest_action.created_at > insights_generated_at:
                is_stale = True

    # Build report data with fresh actions and cached/fresh insights
    report_data = {
        "generated_at": insights_generated_at,
        "is_cached": is_cached,
        "is_stale": is_stale,
        "days_analyzed": days,
        "total_actions": len(unassigned_actions),
        "high_priority_count": high_priority_count,
        "medium_priority_count": medium_priority_count,
        "low_priority_count": low_priority_count,
        "overdue_count": overdue_count,
        "due_this_week_count": due_this_week_count,
        "assigned_in_progress": assigned_in_progress,
        "completed_count": completed_count,
        "completed_this_week": completed_this_week,
        "email_count": cached_data.get("email_count", 0) if is_cached else len(recent_emails) if 'recent_emails' in locals() else 0,
        "insights": insights,
        "unassigned_actions": unassigned_actions  # Keep as ORM objects for template
    }

    return report_data
