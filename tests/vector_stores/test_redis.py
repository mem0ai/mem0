import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("redis")
pytest.importorskip("redisvl")

from mem0.vector_stores.redis import RedisDB


class MockRedisResult(dict):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.__dict__.update(kwargs)


@pytest.fixture
def mock_search_index():
    return MagicMock()


@pytest.fixture
def redis_db(mock_search_index):
    with patch("mem0.vector_stores.redis.redis.Redis.from_url", return_value=MagicMock()), patch(
        "mem0.vector_stores.redis.SearchIndex.from_dict", return_value=mock_search_index
    ):
        return RedisDB(
            redis_url="redis://localhost:6379",
            collection_name="test_collection",
            embedding_model_dims=3,
        )


def test_search_formats_timestamps_in_utc(redis_db, mock_search_index):
    mock_search_index.query.return_value = [
        {
            "memory_id": "memory-id",
            "vector_distance": "0.1",
            "hash": "hash",
            "memory": "hello",
            "metadata": json.dumps({"topic": "test"}),
            "created_at": "0",
            "updated_at": "1",
            "user_id": "user-1",
        }
    ]

    result = redis_db.search("hello", [0.1, 0.2, 0.3], filters={"user_id": "user-1"})[0]

    assert result.payload["created_at"] == "1970-01-01T00:00:00.000000+00:00"
    assert result.payload["updated_at"] == "1970-01-01T00:00:01.000000+00:00"


def test_get_formats_timestamps_in_utc(redis_db, mock_search_index):
    mock_search_index.fetch.return_value = {
        "memory_id": "memory-id",
        "hash": "hash",
        "memory": "hello",
        "metadata": json.dumps({"topic": "test"}),
        "created_at": "0",
        "updated_at": "1",
    }

    result = redis_db.get("memory-id")

    assert result.payload["created_at"] == "1970-01-01T00:00:00.000000+00:00"
    assert result.payload["updated_at"] == "1970-01-01T00:00:01.000000+00:00"


def test_list_formats_timestamps_in_utc(redis_db, mock_search_index):
    mock_search_index.search.return_value = MagicMock(
        docs=[
            MockRedisResult(
                memory_id="memory-id",
                hash="hash",
                memory="hello",
                metadata=json.dumps({"topic": "test"}),
                created_at="0",
                updated_at="1",
                user_id="user-1",
            )
        ]
    )

    result = redis_db.list(filters={"user_id": "user-1"})[0][0]

    assert result.payload["created_at"] == "1970-01-01T00:00:00.000000+00:00"
    assert result.payload["updated_at"] == "1970-01-01T00:00:01.000000+00:00"
    assert datetime.fromisoformat(result.payload["created_at"]).tzinfo == timezone.utc
