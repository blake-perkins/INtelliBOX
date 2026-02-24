"""Helper to log OpenAI API usage telemetry to the database."""

from typing import Optional

from intellibox.utils.logging import logger


def log_api_usage(
    call_type: str,
    api_response,
    email_id: Optional[int] = None,
) -> None:
    """Persist API usage metrics. Best-effort — errors are logged, not raised."""
    try:
        from intellibox.database import get_session
        from intellibox.models import APIUsageLog

        with get_session() as session:
            entry = APIUsageLog(
                call_type=call_type,
                model=api_response.model,
                prompt_tokens=api_response.prompt_tokens,
                completion_tokens=api_response.completion_tokens,
                total_tokens=api_response.total_tokens,
                latency_ms=api_response.latency_ms,
                retry_count=api_response.retry_count,
                status=api_response.status,
                error_message=api_response.error_message or None,
                email_id=email_id,
            )
            session.add(entry)
            session.commit()
    except Exception as e:
        logger.warning(f"Failed to log API usage: {e}")


def log_api_error(
    call_type: str,
    error: Exception,
    model: str = "",
    email_id: Optional[int] = None,
) -> None:
    """Log a failed API call. Best-effort — errors are logged, not raised."""
    try:
        from intellibox.database import get_session
        from intellibox.models import APIUsageLog

        with get_session() as session:
            entry = APIUsageLog(
                call_type=call_type,
                model=model,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                latency_ms=0,
                retry_count=0,
                status="error",
                error_message=str(error)[:500],
                email_id=email_id,
            )
            session.add(entry)
            session.commit()
    except Exception as e:
        logger.warning(f"Failed to log API error: {e}")
