"""Tests for Redis vector store update() — embedding corruption fix.

Regression tests for #4336: when update() is called with vector=None
(metadata-only update), np.array(None) silently creates a 4-byte scalar,
overwriting the real embedding. The fix skips the embedding field entirely
when vector is None.
"""

from datetime import datetime
from unittest.mock import MagicMock

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
