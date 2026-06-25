"""Tests for Redis vector store update() — embedding corruption fix.

Regression tests for #4336: when update() is called with vector=None
(metadata-only update), np.array(None) silently creates a 4-byte scalar,
overwriting the real embedding. The fix skips the embedding field entirely
when vector is None.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import numpy as np
import pytz


def _make_redis_db():
    """Create a RedisDB instance with mocked internals, bypassing __init__
    to avoid the redis module name collision with mem0.vector_stores.redis."""
    from mem0.vector_stores.redis import RedisDB

    db = RedisDB.__new__(RedisDB)
    mock_index = MagicMock()
    db.index = mock_index
    db.schema = {"index": {"prefix": "mem0:test"}}
    return db, mock_index


def test_update_with_none_vector_preserves_embedding():
    """update() with vector=None should not include embedding in the data."""
    db, mock_index = _make_redis_db()

    payload = {
        "hash": "test_hash",
        "data": "updated_data",
        "created_at": datetime.now(pytz.timezone("UTC")).isoformat(),
        "updated_at": datetime.now(pytz.timezone("UTC")).isoformat(),
        "user_id": "test_user",
    }

    db.update(vector_id="test_id", vector=None, payload=payload)

    mock_index.load.assert_called_once()
    call_kwargs = mock_index.load.call_args
    data_dict = call_kwargs[1]["data"][0] if "data" in call_kwargs[1] else call_kwargs[0][0][0]
    assert "embedding" not in data_dict, (
        "embedding should not be in data when vector is None"
    )
    assert data_dict["memory_id"] == "test_id"


def test_update_with_vector_includes_embedding():
    """update() with a real vector should include embedding in the data."""
    db, mock_index = _make_redis_db()

    vector = np.random.rand(1536).tolist()
    payload = {
        "hash": "test_hash",
        "data": "updated_data",
        "created_at": datetime.now(pytz.timezone("UTC")).isoformat(),
        "updated_at": datetime.now(pytz.timezone("UTC")).isoformat(),
        "user_id": "test_user",
    }

    db.update(vector_id="test_id", vector=vector, payload=payload)

    mock_index.load.assert_called_once()
    call_kwargs = mock_index.load.call_args
    data_dict = call_kwargs[1]["data"][0] if "data" in call_kwargs[1] else call_kwargs[0][0][0]
    assert "embedding" in data_dict, (
        "embedding should be in data when vector is provided"
    )
    expected_bytes = np.array(vector, dtype=np.float32).tobytes()
    assert data_dict["embedding"] == expected_bytes


def test_search_with_none_filters_does_not_crash():
    """search() with the base-class default filters=None must run an unfiltered
    query, not raise. Regression: filters.items() on None raised AttributeError
    and reduce() over an empty list raised TypeError. keyword_search() in the
    same file already guards this; search() did not."""
    db, mock_index = _make_redis_db()
    mock_index.query.return_value = []

    assert db.search("query", [0.1, 0.2, 0.3, 0.4], top_k=5, filters=None) == []
    mock_index.query.assert_called_once()


def test_search_with_empty_or_all_none_filters_does_not_crash():
    db, mock_index = _make_redis_db()
    mock_index.query.return_value = []

    assert db.search("query", [0.1, 0.2, 0.3, 0.4], filters={}) == []
    assert db.search("query", [0.1, 0.2, 0.3, 0.4], filters={"user_id": None}) == []


def test_list_with_none_filters_matches_all():
    """list() with no filters must issue a match-all ('*') query, not raise."""
    db, mock_index = _make_redis_db()
    mock_index.search.return_value = MagicMock(docs=[])

    db.list(filters=None)

    query = mock_index.search.call_args[0][0]
    assert query.query_string() == "*"


def test_list_with_filter_builds_query():
    """A real filter is still translated into a tag query (no regression)."""
    db, mock_index = _make_redis_db()
    mock_index.search.return_value = MagicMock(docs=[])

    db.list(filters={"user_id": "alice"})

    query = mock_index.search.call_args[0][0]
    assert query.query_string() == "@user_id:{alice}"


def test_create_col_keeps_distinct_dims_across_instances():
    """Building the schema for two collections with different embedding
    dimensions must keep them distinct. Regression: DEFAULT_FIELDS.copy() is a
    shallow copy, so the shared "embedding" field dict was mutated in place and
    the second create_col() clobbered the first one's dims (and the module
    global)."""
    import mem0.vector_stores.redis as redis_module

    db, _ = _make_redis_db()
    db.client = MagicMock()

    captured = []

    def capture_schema(schema):
        captured.append(schema)
        return MagicMock()

    with patch.object(redis_module.SearchIndex, "from_dict", side_effect=capture_schema):
        db.create_col(name="col_384", vector_size=384)
        db.create_col(name="col_1536", vector_size=1536)

    assert captured[0]["fields"][-1]["attrs"]["dims"] == 384
    assert captured[1]["fields"][-1]["attrs"]["dims"] == 1536
    # the module-level default must never be mutated by building a schema
    assert "dims" not in redis_module.DEFAULT_FIELDS[-1]["attrs"]


def test_init_keeps_distinct_dims_from_module_global():
    """__init__ must stamp the requested dims into the index schema without
    mutating the shared module-level DEFAULT_FIELDS. The create_col test above
    covers the other deepcopy site; all other tests build RedisDB via __new__
    and so skip __init__, leaving this call site otherwise uncovered."""
    import mem0.vector_stores.redis as redis_module
    from mem0.vector_stores.redis import RedisDB

    captured = []

    def capture_schema(schema):
        captured.append(schema)
        return MagicMock()

    with (
        patch("mem0.vector_stores.redis.redis.Redis.from_url", return_value=MagicMock()),
        patch.object(redis_module.SearchIndex, "from_dict", side_effect=capture_schema),
    ):
        RedisDB("redis://localhost:6379", "col_384", 384)

    assert captured[0]["fields"][-1]["attrs"]["dims"] == 384
    # the module-level default must never be mutated by constructing an instance
    assert "dims" not in redis_module.DEFAULT_FIELDS[-1]["attrs"]


def test_get_returns_none_for_missing_id():
    """get() must return None for a missing id.

    redisvl's SearchIndex.fetch() returns None when the id is not found, so the
    old code raised ``TypeError: 'NoneType' object is not subscriptable`` on
    ``result["hash"]``. Every other vector store returns None for a missing id,
    and Memory relies on it (``if existing_memory is None``), so get() must too.
    """
    db, mock_index = _make_redis_db()
    mock_index.fetch.return_value = None

    assert db.get("missing_id") is None
    mock_index.fetch.assert_called_once_with("missing_id")


def test_insert_entity_payload_without_hash_and_created_at():
    """insert() must not crash on entity payloads that lack hash/created_at."""
    db, mock_index = _make_redis_db()

    entity_payload = {
        "data": "OpenAI",
        "entity_type": "organization",
        "linked_memory_ids": ["mem-1"],
        "user_id": "test_user",
    }

    db.insert(
        vectors=[[0.1, 0.2, 0.3]],
        payloads=[entity_payload],
        ids=["entity-1"],
    )

    mock_index.load.assert_called_once()
    data = mock_index.load.call_args[0][0]
    assert data[0]["memory_id"] == "entity-1"
    assert data[0]["memory"] == "OpenAI"
    assert data[0]["hash"] == ""
    assert data[0]["created_at"] == 0


def test_update_entity_payload_without_hash_and_timestamps():
    """update() must not crash on entity payloads that lack hash/created_at/updated_at."""
    db, mock_index = _make_redis_db()

    entity_payload = {
        "data": "OpenAI",
        "entity_type": "organization",
        "linked_memory_ids": ["mem-1"],
        "user_id": "test_user",
    }

    db.update(vector_id="entity-1", vector=[0.1, 0.2, 0.3], payload=entity_payload)

    mock_index.load.assert_called_once()
    call_kwargs = mock_index.load.call_args
    data_dict = call_kwargs[1]["data"][0] if "data" in call_kwargs[1] else call_kwargs[0][0][0]
    assert data_dict["memory_id"] == "entity-1"
    assert data_dict["memory"] == "OpenAI"
    assert data_dict["hash"] == ""
    assert data_dict["created_at"] == 0
    assert data_dict["updated_at"] == 0
