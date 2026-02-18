"""AI processing pipeline for emails."""

import json
import time
from typing import Optional

from sqlalchemy.orm import Session

from emailtools.config import settings
from emailtools.models import Email, ProcessingLog
from emailtools.utils.datetime_utils import utcnow
from emailtools.utils.logging import logger


def get_ai_client():
    """Get AI client (real or mock based on API key)."""
    # Check if API key is set to a real value
    if settings.openai_api_key and not settings.openai_api_key.startswith("sk-placeholder"):
        from emailtools.ai.client import ai_client
        return ai_client
    else:
        from emailtools.ai.mock_client import mock_ai_client
        logger.info("Using DEMO MODE: No real API calls will be made")
        return mock_ai_client


def process_email_with_ai(email: Email, session: Session) -> int:
    """
    Process a single email with AI to extract actions.

    Args:
        email: Email object to process
        session: Database session

    Returns:
        Number of actions created
    """
    if email.processed:
        logger.info(f"Email ID {email.id} already processed, skipping")
        return 0

    try:
        # Get AI client (real or mock)
        client = get_ai_client()

        # Extract actions using AI
        action_dicts, raw_response = client.extract_actions(email)

        # Create Action objects
        actions = client.create_action_objects(email, action_dicts, raw_response)

        # Add actions to session
        for action in actions:
            session.add(action)

        # Mark email as processed
        email.processed = True
        email.processed_at = utcnow()

        # Log success
        log_entry = ProcessingLog(
            email_id=email.id,
            event_type="ai_parsed",
            status="success",
            message=f"Extracted {len(actions)} action(s)",
            event_metadata=json.dumps({
                "action_count": len(actions),
                "confidence_scores": [a.confidence_score for a in actions if a.confidence_score]
            })
        )
        session.add(log_entry)
        session.commit()

        logger.info(f"Successfully processed email ID {email.id}: {len(actions)} action(s) created")
        return len(actions)

    except Exception as e:
        logger.error(f"Failed to process email ID {email.id} with AI: {e}")
        session.rollback()

        # Log failure
        log_entry = ProcessingLog(
            email_id=email.id,
            event_type="ai_parsed",
            status="failure",
            message=f"AI processing failed: {str(e)[:200]}",
            event_metadata=json.dumps({"error": str(e)})
        )
        session.add(log_entry)
        session.commit()

        return 0


def process_unprocessed_emails(
    session: Session,
    limit: Optional[int] = None,
    batch_size: Optional[int] = None,
    batch_delay: Optional[float] = None,
) -> tuple[int, int]:
    """
    Process all unprocessed emails with AI in rate-limited batches.

    Args:
        session: Database session
        limit: Optional limit on number of emails to process
        batch_size: Emails per batch before pausing (default from config)
        batch_delay: Seconds to wait between batches (default from config)

    Returns:
        Tuple of (emails_processed, total_actions_created)
    """
    if batch_size is None:
        batch_size = settings.ai_batch_size
    if batch_delay is None:
        batch_delay = settings.ai_batch_delay

    # Query unprocessed emails
    query = session.query(Email).filter(Email.processed == False).order_by(Email.received_date)

    if limit:
        query = query.limit(limit)

    unprocessed_emails = query.all()

    if not unprocessed_emails:
        logger.info("No unprocessed emails found")
        return 0, 0

    total = len(unprocessed_emails)
    logger.info(f"Processing {total} unprocessed email(s) with AI (batch_size={batch_size}, delay={batch_delay}s)")

    emails_processed = 0
    total_actions = 0

    for i, email in enumerate(unprocessed_emails):
        actions_count = process_email_with_ai(email, session)
        if actions_count >= 0:  # Successful processing (0 actions is valid)
            emails_processed += 1
            total_actions += actions_count

        # Rate limit: pause between batches
        if batch_size > 0 and (i + 1) % batch_size == 0 and (i + 1) < total:
            logger.info(f"Batch {(i + 1) // batch_size} complete ({i + 1}/{total}), waiting {batch_delay}s...")
            time.sleep(batch_delay)

    logger.info(f"AI processing complete: {emails_processed} emails, {total_actions} actions")
    return emails_processed, total_actions
