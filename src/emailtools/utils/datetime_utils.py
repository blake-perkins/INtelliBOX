"""UTC datetime utilities — drop-in replacement for deprecated datetime.utcnow()."""

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Return the current UTC time as a naive datetime (no tzinfo).

    This is a safe replacement for the deprecated ``datetime.utcnow()``.
    It uses ``datetime.now(timezone.utc)`` internally (the Python 3.12+
    recommended approach) but strips the timezone info so the result is
    compatible with SQLite and existing naive-datetime comparisons
    throughout the codebase.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
