"""Timezone-aware UTC datetime utilities."""

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Return the current UTC time as a timezone-aware datetime.

    Replaces deprecated ``datetime.utcnow()`` which returns naive datetimes.
    Uses ``datetime.now(timezone.utc)`` as recommended by Python 3.12+.
    """
    return datetime.now(timezone.utc)
