"""Tests for the UTC datetime utility."""

from datetime import datetime, timezone


def test_utcnow_returns_datetime():
    """utcnow() returns a datetime instance."""
    from intellibox.utils.datetime_utils import utcnow
    result = utcnow()
    assert isinstance(result, datetime)


def test_utcnow_returns_naive_datetime():
    """utcnow() returns a naive datetime (tzinfo is None) for SQLite compat."""
    from intellibox.utils.datetime_utils import utcnow
    result = utcnow()
    assert result.tzinfo is None


def test_utcnow_close_to_now():
    """utcnow() returns a time within 1 second of datetime.now(UTC)."""
    from intellibox.utils.datetime_utils import utcnow
    result = utcnow()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    delta = abs((now - result).total_seconds())
    assert delta < 1.0


def test_utcnow_is_not_local_time():
    """utcnow() returns UTC, not local time (delta from aware UTC < 1s)."""
    from intellibox.utils.datetime_utils import utcnow
    result = utcnow()
    utc_now = datetime.now(timezone.utc).replace(tzinfo=None)
    # Should be within 1 second of actual UTC
    assert abs((utc_now - result).total_seconds()) < 1.0


def test_utcnow_comparable_with_naive_datetimes():
    """utcnow() result can be subtracted from other naive datetimes."""
    from intellibox.utils.datetime_utils import utcnow
    result = utcnow()
    other = datetime(2020, 1, 1)
    delta = result - other
    assert delta.total_seconds() > 0
