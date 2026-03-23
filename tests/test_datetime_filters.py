"""Tests for datetime range filtering in Memory.search() and Memory.get_all()."""

from datetime import datetime, timezone

import pytest

from mem0.memory.main import _parse_datetime_to_epoch, _rewrite_datetime_filters


class TestParseDatetimeToEpoch:
    def test_float_passthrough(self):
        assert _parse_datetime_to_epoch(1700000000.0) == 1700000000.0

    def test_int_passthrough(self):
        assert _parse_datetime_to_epoch(1700000000) == 1700000000.0

    def test_datetime_object(self):
        dt = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
        assert _parse_datetime_to_epoch(dt) == dt.timestamp()

    def test_iso_string(self):
        result = _parse_datetime_to_epoch("2026-03-01T00:00:00+00:00")
        expected = datetime(2026, 3, 1, tzinfo=timezone.utc).timestamp()
        assert result == expected

    def test_date_only_string(self):
        result = _parse_datetime_to_epoch("2026-03-01")
        expected = datetime(2026, 3, 1).timestamp()
        assert result == expected

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError, match="Cannot parse datetime"):
            _parse_datetime_to_epoch([1, 2, 3])

    def test_invalid_string_raises(self):
        with pytest.raises(ValueError):
            _parse_datetime_to_epoch("not-a-date")


class TestRewriteDatetimeFilters:
    def test_created_at_gte_rewritten(self):
        filters = {"created_at": {"gte": "2026-01-01"}}
        result = _rewrite_datetime_filters(filters)
        assert "created_at" not in result
        assert "created_at_timestamp" in result
        assert isinstance(result["created_at_timestamp"]["gte"], float)

    def test_created_at_range_rewritten(self):
        filters = {"created_at": {"gte": "2026-01-01", "lte": "2026-03-01"}}
        result = _rewrite_datetime_filters(filters)
        assert "created_at_timestamp" in result
        assert "gte" in result["created_at_timestamp"]
        assert "lte" in result["created_at_timestamp"]

    def test_updated_at_rewritten(self):
        filters = {"updated_at": {"gt": "2026-02-01"}}
        result = _rewrite_datetime_filters(filters)
        assert "updated_at_timestamp" in result

    def test_non_datetime_field_unchanged(self):
        filters = {"user_id": "alice", "score": {"gte": 0.5}}
        result = _rewrite_datetime_filters(filters)
        assert result == filters

    def test_exact_match_not_rewritten(self):
        filters = {"created_at": "2026-01-01T00:00:00+00:00"}
        result = _rewrite_datetime_filters(filters)
        assert "created_at" in result
        assert "created_at_timestamp" not in result

    def test_empty_filters(self):
        assert _rewrite_datetime_filters({}) == {}
        assert _rewrite_datetime_filters(None) is None

    def test_numeric_epoch_passthrough(self):
        filters = {"created_at": {"gte": 1700000000.0}}
        result = _rewrite_datetime_filters(filters)
        assert result["created_at_timestamp"]["gte"] == 1700000000.0
