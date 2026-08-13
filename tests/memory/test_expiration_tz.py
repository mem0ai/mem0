"""Regression tests for expiration-date timezone handling (#6931).

The stored expiration value is a calendar date taken from the caller's
wall-clock (``value.date()``), but the expiry check compared it against the
UTC calendar day. Around every date boundary the decision drifted by the
local UTC offset: a memory could stay visible up to one day too long, or
expire up to one day early.
"""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

from mem0.memory.main import _normalize_expiration_date, _payload_is_expired

_UTC_PLUS_8 = timezone(timedelta(hours=8))


class _FrozenDatetime(datetime):
    """datetime subclass whose ``now()`` returns a frozen wall-clock instant.

    ``now(tz=...)`` converts the frozen local instant to the requested zone,
    mirroring the stdlib's behavior of ``datetime.now(timezone.utc)``.
    """

    frozen_local: datetime | None = None

    @classmethod
    def set_now(cls, local_dt: datetime) -> None:
        cls.frozen_local = local_dt

    @classmethod
    def now(cls, tz=None):
        if cls.frozen_local is None:
            return datetime.now(tz)
        if tz is not None:
            return cls.frozen_local.astimezone(tz)
        return cls.frozen_local


def _freeze(local_dt: datetime):
    _FrozenDatetime.set_now(local_dt)
    return patch("mem0.memory.main.datetime", _FrozenDatetime)


def test_expired_uses_local_calendar_day_not_utc():
    """Local date has advanced past the expiration while UTC has not.

    Local time is 2026-08-14 00:30 (+08:00) == 2026-08-13T16:30Z. The memory
    expires on 2026-08-13, so it must be considered expired — but comparing
    against the UTC calendar day (still 08-13) kept it visible for another
    7.5 hours.
    """
    with _freeze(datetime(2026, 8, 14, 0, 30, tzinfo=_UTC_PLUS_8)):
        assert _payload_is_expired({"expiration_date": "2026-08-13"})


def test_not_expired_on_expiration_day():
    """Still valid on the expiration date itself (local calendar day)."""
    with _freeze(datetime(2026, 8, 13, 23, 59, tzinfo=_UTC_PLUS_8)):
        assert not _payload_is_expired({"expiration_date": "2026-08-13"})


def test_no_expiration_not_expired():
    assert not _payload_is_expired({})
    assert not _payload_is_expired({"expiration_date": None})


def test_normalize_preserves_caller_calendar_day():
    """An aware datetime keeps the caller's wall-clock calendar day."""
    aware = datetime(2026, 8, 13, 23, 30, tzinfo=_UTC_PLUS_8)
    assert _normalize_expiration_date(aware) == "2026-08-13"


def test_normalize_accepts_plain_date_and_string():
    assert _normalize_expiration_date(date(2026, 8, 13)) == "2026-08-13"
    assert _normalize_expiration_date("2026-08-13") == "2026-08-13"
    assert _normalize_expiration_date(None) is None
