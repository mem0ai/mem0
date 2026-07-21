"""Regression tests for process_telemetry_filters return contract and None entity ids."""

import hashlib

from mem0.memory.utils import process_telemetry_filters


def test_none_filters_returns_two_tuple():
    keys, encoded = process_telemetry_filters(None)
    assert keys == []
    assert encoded == {}


def test_empty_filters_returns_two_tuple():
    keys, encoded = process_telemetry_filters({})
    assert keys == []
    assert encoded == {}


def test_skips_none_entity_ids_but_keeps_other_keys():
    keys, encoded = process_telemetry_filters({"user_id": None, "agent_id": "a1", "category": "x"})
    assert "user_id" in keys
    assert "agent_id" in keys
    assert "user_id" not in encoded
    assert encoded["agent_id"] == hashlib.md5(b"a1").hexdigest()


def test_hashes_string_entity_ids():
    keys, encoded = process_telemetry_filters({"user_id": "u1"})
    assert keys == ["user_id"]
    assert encoded["user_id"] == hashlib.md5(b"u1").hexdigest()


def test_drop_null_entity_ids_helper():
    from mem0.memory.main import _drop_null_entity_ids

    out = _drop_null_entity_ids({"user_id": None, "agent_id": "a1", "foo": 1})
    assert "user_id" not in out
    assert out["agent_id"] == "a1"
    assert out["foo"] == 1
    assert _drop_null_entity_ids(None) == {}
