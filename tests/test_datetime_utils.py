"""Tests for the UTC datetime utility."""

from datetime import datetime, timezone


def test_utcnow_returns_datetime():
    """utcnow() returns a datetime instance."""
    from emailtools.utils.datetime_utils import utcnow
    result = utcnow()
    assert isinstance(result, datetime)


def test_utcnow_returns_aware_datetime():
    """utcnow() returns a timezone-aware datetime (tzinfo is not None)."""
    from emailtools.utils.datetime_utils import utcnow
    result = utcnow()
    assert result.tzinfo is not None


def test_utcnow_is_utc():
    """utcnow() returns a datetime in the UTC timezone."""
    from emailtools.utils.datetime_utils import utcnow
    result = utcnow()
    assert result.tzinfo == timezone.utc


def test_utcnow_close_to_now():
    """utcnow() returns a time within 1 second of datetime.now(UTC)."""
    from emailtools.utils.datetime_utils import utcnow
    result = utcnow()
    now = datetime.now(timezone.utc)
    delta = abs((now - result).total_seconds())
    assert delta < 1.0
