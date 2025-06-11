from dataclasses import dataclass
from typing import Dict, List, Optional
from unittest.mock import MagicMock, call, patch

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
    return UpstashVector(client=mock_index.return_value, collection_name="ns")


@pytest.fixture
def upstash_instance_with_embeddings(mock_index):
    return UpstashVector(client=mock_index.return_value, collection_name="ns", enable_embeddings=True)


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

    upstash_instance.client.query_many.return_value = [mock_result]

    vectors = [[0.1, 0.2, 0.3]]
    results = upstash_instance.search(
        query="hello world",
        vectors=vectors,
        limit=2,
        filters={"age": 30, "name": "John"},
    )

    upstash_instance.client.query_many.assert_called_once_with(
        queries=[
            {
                "vector": vectors[0],
                "top_k": 2,
                "namespace": "ns",
                "include_metadata": True,
                "filter": 'age = 30 AND name = "John"',
            }
        ]
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
        id="id1",
        vector=new_vector,
        data=None,
        metadata={"name": "updated_vector"},
        namespace="ns",
    )


def test_get_vector(upstash_instance):
    mock_result = [QueryResult(id="id1", score=None, vector=None, metadata={"name": "vector1"}, data=None)]
    upstash_instance.client.fetch.return_value = mock_result

    result = upstash_instance.get(vector_id="id1")

    upstash_instance.client.fetch.assert_called_once_with(ids=["id1"], namespace="ns", include_metadata=True)

    assert result.id == "id1"
    assert result.payload == {"name": "vector1"}


def test_list_vectors(upstash_instance):
    mock_result = [
        QueryResult(id="id1", score=None, vector=None, metadata={"name": "vector1"}, data=None),
        QueryResult(id="id2", score=None, vector=None, metadata={"name": "vector2"}, data=None),
        QueryResult(id="id3", score=None, vector=None, metadata={"name": "vector3"}, data=None),
    ]
    handler = MagicMock()

    upstash_instance.client.info.return_value.dimension = 10
    upstash_instance.client.resumable_query.return_value = (mock_result[0:1], handler)
    handler.fetch_next.side_effect = [mock_result[1:2], mock_result[2:3], []]

    filters = {"age": 30, "name": "John"}
    print("filters", filters)
    [results] = upstash_instance.list(filters=filters, limit=15)

    upstash_instance.client.info.return_value = {
        "dimension": 10,
    }

    upstash_instance.client.resumable_query.assert_called_once_with(
        vector=[1.0] * 10,
        filter='age = 30 AND name = "John"',
        include_metadata=True,
        namespace="ns",
        top_k=100,
    )

    handler.fetch_next.assert_has_calls([call(100), call(100), call(100)])
    handler.__exit__.assert_called_once()

    assert len(results) == len(mock_result)
    assert results[0].id == "id1"
    assert results[0].payload == {"name": "vector1"}


def test_insert_vectors_with_embeddings(upstash_instance_with_embeddings, mock_index):
    vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    payloads = [
        {"name": "vector1", "data": "data1"},
        {"name": "vector2", "data": "data2"},
    ]
    ids = ["id1", "id2"]

    upstash_instance_with_embeddings.insert(vectors=vectors, payloads=payloads, ids=ids)

    upstash_instance_with_embeddings.client.upsert.assert_called_once_with(
        vectors=[
            {
                "id": "id1",
                # Uses the data field instead of using vectors
                "data": "data1",
                "metadata": {"name": "vector1", "data": "data1"},
            },
            {
                "id": "id2",
                "data": "data2",
                "metadata": {"name": "vector2", "data": "data2"},
            },
        ],
        namespace="ns",
    )


def test_search_vectors_with_embeddings(upstash_instance_with_embeddings, mock_index):
    mock_result = [
        QueryResult(id="id1", score=0.1, vector=None, metadata={"name": "vector1"}, data="data1"),
        QueryResult(id="id2", score=0.2, vector=None, metadata={"name": "vector2"}, data="data2"),
    ]

    upstash_instance_with_embeddings.client.query.return_value = mock_result

    results = upstash_instance_with_embeddings.search(
        query="hello world",
        vectors=[],
        limit=2,
        filters={"age": 30, "name": "John"},
    )

    upstash_instance_with_embeddings.client.query.assert_called_once_with(
        # Uses the data field instead of using vectors
        data="hello world",
        top_k=2,
        filter='age = 30 AND name = "John"',
        include_metadata=True,
        namespace="ns",
    )

    assert len(results) == 2
    assert results[0].id == "id1"
    assert results[0].score == 0.1
    assert results[0].payload == {"name": "vector1"}


def test_update_vector_with_embeddings(upstash_instance_with_embeddings):
    vector_id = "id1"
    new_payload = {"name": "updated_vector", "data": "updated_data"}

    upstash_instance_with_embeddings.update(vector_id=vector_id, payload=new_payload)

    upstash_instance_with_embeddings.client.update.assert_called_once_with(
        id="id1",
        vector=None,
        data="updated_data",
        metadata={"name": "updated_vector", "data": "updated_data"},
        namespace="ns",
    )


def test_insert_vectors_with_embeddings_missing_data(upstash_instance_with_embeddings):
    vectors = [[0.1, 0.2, 0.3]]
    payloads = [{"name": "vector1"}]  # Missing data field
    ids = ["id1"]

    with pytest.raises(
        ValueError,
        match="When embeddings are enabled, all payloads must contain a 'data' field",
    ):
        upstash_instance_with_embeddings.insert(vectors=vectors, payloads=payloads, ids=ids)


def test_update_vector_with_embeddings_missing_data(upstash_instance_with_embeddings):
    # Should still work, data is not required for update
    vector_id = "id1"
    new_payload = {"name": "updated_vector"}  # Missing data field

    upstash_instance_with_embeddings.update(vector_id=vector_id, payload=new_payload)

    upstash_instance_with_embeddings.client.update.assert_called_once_with(
        id="id1",
        vector=None,
        data=None,
        metadata={"name": "updated_vector"},
        namespace="ns",
    )


def test_list_cols(upstash_instance):
    mock_namespaces = ["ns1", "ns2", "ns3"]
    upstash_instance.client.list_namespaces.return_value = mock_namespaces

    result = upstash_instance.list_cols()

    upstash_instance.client.list_namespaces.assert_called_once()
    assert result == mock_namespaces


def test_delete_col(upstash_instance):
    upstash_instance.delete_col()
    upstash_instance.client.reset.assert_called_once_with(namespace="ns")


def test_col_info(upstash_instance):
    mock_info = {
        "dimension": 10,
        "total_vectors": 100,
        "pending_vectors": 0,
        "disk_size": 1024,
    }
    upstash_instance.client.info.return_value = mock_info

    result = upstash_instance.col_info()

    upstash_instance.client.info.assert_called_once()
    assert result == mock_info


def test_get_vector_not_found(upstash_instance):
    upstash_instance.client.fetch.return_value = []

    result = upstash_instance.get(vector_id="nonexistent")

    upstash_instance.client.fetch.assert_called_once_with(ids=["nonexistent"], namespace="ns", include_metadata=True)
    assert result is None


def test_search_vectors_empty_filters(upstash_instance):
    mock_result = [QueryResult(id="id1", score=0.1, vector=None, metadata={"name": "vector1"}, data=None)]
    upstash_instance.client.query_many.return_value = [mock_result]

    vectors = [[0.1, 0.2, 0.3]]
    results = upstash_instance.search(
        query="hello world",
        vectors=vectors,
        limit=1,
        filters=None,
    )

    upstash_instance.client.query_many.assert_called_once_with(
        queries=[
            {
                "vector": vectors[0],
                "top_k": 1,
                "namespace": "ns",
                "include_metadata": True,
                "filter": "",
            }
        ]
    )

    assert len(results) == 1
    assert results[0].id == "id1"


def test_insert_vectors_no_payloads(upstash_instance):
    vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    ids = ["id1", "id2"]

    upstash_instance.insert(vectors=vectors, ids=ids)

    upstash_instance.client.upsert.assert_called_once_with(
        vectors=[
            {"id": "id1", "vector": [0.1, 0.2, 0.3], "metadata": None},
            {"id": "id2", "vector": [0.4, 0.5, 0.6], "metadata": None},
        ],
        namespace="ns",
    )


def test_insert_vectors_no_ids(upstash_instance):
    vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    payloads = [{"name": "vector1"}, {"name": "vector2"}]

    upstash_instance.insert(vectors=vectors, payloads=payloads)

    upstash_instance.client.upsert.assert_called_once_with(
        vectors=[
            {"id": None, "vector": [0.1, 0.2, 0.3], "metadata": {"name": "vector1"}},
            {"id": None, "vector": [0.4, 0.5, 0.6], "metadata": {"name": "vector2"}},
        ],
        namespace="ns",
    )
