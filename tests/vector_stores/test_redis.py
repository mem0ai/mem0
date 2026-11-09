"""Tests for Redis vector store update() — embedding corruption fix.

Regression tests for #4336: when update() is called with vector=None
(metadata-only update), np.array(None) silently creates a 4-byte scalar,
overwriting the real embedding. The fix skips the embedding field entirely
when vector is None.
"""

import json
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
    db.client = MagicMock()
    db.client.eval.return_value = 1
    return db, mock_index


def _written_fields(db):
    """Decode the field/value pairs update() passed to its exists-guarded HSET script."""
    _, _, _, *flat = db.client.eval.call_args[0]
    return dict(zip(flat[::2], flat[1::2]))


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

    assert db.update(vector_id="test_id", vector=None, payload=payload) is True

    data_dict = _written_fields(db)
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

    data_dict = _written_fields(db)
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

    data_dict = _written_fields(db)
    assert data_dict["memory_id"] == "entity-1"
    assert data_dict["memory"] == "OpenAI"
    assert data_dict["hash"] == ""
    assert data_dict["created_at"] == 0
    assert data_dict["updated_at"] == 0


def test_update_missing_id_returns_false_without_writing():
    """A memory deleted after Memory read it must stay deleted: the only write is the
    script that checks the key exists, and a missing key reports False."""
    db, mock_index = _make_redis_db()
    db.client.eval.return_value = 0

    assert db.update(vector_id="gone", vector=[0.1, 0.2], payload={"data": "d"}) is False
    script, numkeys, key = db.client.eval.call_args[0][:3]
    assert (numkeys, key) == (1, "mem0:test:gone") and "EXISTS" in script
    mock_index.load.assert_not_called()
    db.client.hset.assert_not_called()


def test_update_existing_id_writes_the_same_fields_as_before():
    db, _ = _make_redis_db()
    created_at, updated_at = "2024-01-01T00:00:00+00:00", "2024-01-02T00:00:00+00:00"
    payload = {"hash": "h", "data": "d", "created_at": created_at, "updated_at": updated_at, "user_id": "u", "tag": "t"}

    assert db.update(vector_id="m1", vector=[0.5, 0.25], payload=payload) is True
    assert db.client.eval.call_args[0][2] == "mem0:test:m1"
    assert _written_fields(db) == {
        "memory_id": "m1", "hash": "h", "memory": "d", "created_at": 1704067200, "updated_at": 1704153600,
        "embedding": np.array([0.5, 0.25], dtype=np.float32).tobytes(), "user_id": "u",
        "metadata": json.dumps({"tag": "t"}),
    }


def test_update_uses_watch_multi_exec_when_acl_denies_scripting():
    """With @scripting denied, EVAL fails with NOPERM and update() writes inside WATCH/MULTI/EXEC: if the
    key changes after the check, EXEC aborts and the loop re-checks, so a concurrent delete wins."""
    import redis

    def run(exists, execute):
        db, _ = _make_redis_db()
        db.client.eval.side_effect = redis.exceptions.NoPermissionError("NOPERM no permissions to run 'eval'")
        db.client.pipeline.return_value.__enter__.return_value = pipe = MagicMock()
        pipe.exists.side_effect, pipe.execute.side_effect = exists, execute
        return db.update(vector_id="m1", vector=None, payload={"data": "d"}), pipe

    result, pipe = run(exists=[0], execute=None)
    assert result is False and not pipe.hset.called
    result, pipe = run(exists=[1], execute=[[1]])
    assert result is True and pipe.watch.call_args[0] == ("mem0:test:m1",)
    assert pipe.hset.call_args[0] == ("mem0:test:m1",) and pipe.hset.call_args[1]["mapping"]["memory"] == "d"
    result, pipe = run(exists=[1, 1], execute=[redis.exceptions.WatchError(), [1]])
    assert result is True and pipe.watch.call_count == 2
    result, pipe = run(exists=[1, 0], execute=[redis.exceptions.WatchError()])
    assert result is False and pipe.execute.call_count == 1
