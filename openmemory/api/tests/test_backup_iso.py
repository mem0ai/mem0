import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from datetime import datetime, timezone, timedelta

from app.routers.backup import _iso


def test_iso_none_input():
    assert _iso(None) is None


def test_iso_naive_datetime():
    dt = datetime(2026, 1, 1, 10, 0, 0)  # naive
    result = _iso(dt)
    assert result == "2026-01-01T10:00:00+00:00"


def test_iso_aware_non_utc():
    dt = datetime(
        2026, 1, 1, 10, 0, 0,
        tzinfo=timezone(timedelta(hours=5, minutes=30))  # IST
    )
    result = _iso(dt)
    # 10:00 IST -> 04:30 UTC
    assert result == "2026-01-01T04:30:00+00:00"


def test_iso_aware_utc():
    dt = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    result = _iso(dt)
    assert result == "2026-01-01T10:00:00+00:00"