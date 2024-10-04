from dataclasses import dataclass
from typing import Dict, List, Optional
from unittest.mock import patch

import pytest

from mem0.vector_stores.upstash_vector import UpstashVector


@dataclass
class QueryResult:
    id: str
    score: Optional[float]
    vector: Optional[List[float]] = None
    metadata: Optional[Dict] = None
    data: Optional[str] = None


@pytest.fixture
def mock_index():
    with patch("upstash_vector.Index") as mock_index:
        yield mock_index


@pytest.fixture
def upstash_instance(mock_index):
    return UpstashVector(client=mock_index.return_value, namespace="ns")


def test_insert_vectors(upstash_instance, mock_index):
    vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    payloads = [{"name": "vector1"}, {"name": "vector2"}]
    ids = ["id1", "id2"]

    upstash_instance.insert(vectors=vectors, payloads=payloads, ids=ids)

    upstash_instance.client.upsert.assert_called_once_with(
        vectors=[
            {"id": "id1", "vector": [0.1, 0.2, 0.3], "metadata": {"name": "vector1"}},
            {"id": "id2", "vector": [0.4, 0.5, 0.6], "metadata": {"name": "vector2"}},
        ],
        namespace="ns",
    )


def test_search_vectors(upstash_instance, mock_index):
    mock_result = [
        QueryResult(id="id1", score=0.1, vector=None, metadata={"name": "vector1"}, data=None),
        QueryResult(id="id2", score=0.2, vector=None, metadata={"name": "vector2"}, data=None),
    ]

    upstash_instance.client.query.return_value = mock_result

    query = [[0.1, 0.2, 0.3]]
    results = upstash_instance.search(query=query, limit=2, filters={"age": 30, "name": "John"})

    upstash_instance.client.query.assert_called_once_with(
        vector=query, top_k=2, namespace="ns", include_metadata=True, filter='age = 30 AND name = "John"'
    )

    assert len(results) == 2
    assert results[0].id == "id1"
    assert results[0].score == 0.1
    assert results[0].payload == {"name": "vector1"}


def test_delete_vector(upstash_instance):
    vector_id = "id1"

    upstash_instance.delete(vector_id=vector_id)

    upstash_instance.client.delete.assert_called_once_with(ids=[vector_id], namespace="ns")


def test_update_vector(upstash_instance):
    vector_id = "id1"
    new_vector = [0.7, 0.8, 0.9]
    new_payload = {"name": "updated_vector"}

    upstash_instance.update(vector_id=vector_id, vector=new_vector, payload=new_payload)

    upstash_instance.client.update.assert_called_once_with(
        id="id1", vector=[0.7, 0.8, 0.9], metadata={"name": "updated_vector"}, namespace="ns"
    )


def test_get_vector(upstash_instance):
    mock_result = [QueryResult(id="id1", score=None, vector=None, metadata={"name": "vector1"}, data=None)]
    upstash_instance.client.fetch.return_value = mock_result

    result = upstash_instance.get(vector_id="id1")

    upstash_instance.client.fetch.assert_called_once_with(ids=["id1"], namespace="ns", include_metadata=True)

    assert result.id == "id1"
    assert result.payload == {"name": "vector1"}
