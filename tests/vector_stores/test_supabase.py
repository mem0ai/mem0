from unittest.mock import Mock, patch

import pytest

from mem0.configs.vector_stores.supabase import IndexMeasure, IndexMethod
from mem0.vector_stores.supabase import Supabase


@pytest.fixture
def mock_vecs_client():
    with patch("vecs.create_client") as mock_client:
        yield mock_client


@pytest.fixture
def mock_collection():
    collection = Mock()
    collection.name = "test_collection"
    collection.vectors = 100
    collection.dimension = 1536
    collection.index_method = "hnsw"
    collection.distance_metric = "cosine_distance"
    collection.describe.return_value = collection
    return collection


@pytest.fixture
def supabase_instance(mock_vecs_client, mock_collection):
    # Set up the mock client to return our mock collection
    mock_vecs_client.return_value.get_or_create_collection.return_value = mock_collection
    mock_vecs_client.return_value.list_collections.return_value = ["test_collection"]

    instance = Supabase(
        connection_string="postgresql://user:password@localhost:5432/test",
        collection_name="test_collection",
        embedding_model_dims=1536,
        index_method=IndexMethod.HNSW,
        index_measure=IndexMeasure.COSINE,
    )

    # Manually set the collection attribute since we're mocking the initialization
    instance.collection = mock_collection
    return instance


def test_create_col(supabase_instance, mock_vecs_client, mock_collection):
    supabase_instance.create_col(1536)

    mock_vecs_client.return_value.get_or_create_collection.assert_called_with(name="test_collection", dimension=1536)
    mock_collection.create_index.assert_called_with(method="hnsw", measure="cosine_distance")


def test_insert_vectors(supabase_instance, mock_collection):
    vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    payloads = [{"name": "vector1"}, {"name": "vector2"}]
    ids = ["id1", "id2"]

    supabase_instance.insert(vectors=vectors, payloads=payloads, ids=ids)

    expected_records = [("id1", [0.1, 0.2, 0.3], {"name": "vector1"}), ("id2", [0.4, 0.5, 0.6], {"name": "vector2"})]
    mock_collection.upsert.assert_called_once_with(expected_records)


def test_search_vectors(supabase_instance, mock_collection):
    mock_results = [("id1", 0.9, {"name": "vector1"}), ("id2", 0.8, {"name": "vector2"})]
    mock_collection.query.return_value = mock_results

    vectors = [[0.1, 0.2, 0.3]]
    filters = {"category": "test"}
    results = supabase_instance.search(query="", vectors=vectors, limit=2, filters=filters)

    mock_collection.query.assert_called_once_with(
        data=vectors, limit=2, filters={"category": {"$eq": "test"}}, include_metadata=True, include_value=True
    )

    assert len(results) == 2
    assert results[0].id == "id1"
    assert results[0].score == 0.9
    assert results[0].payload == {"name": "vector1"}


def test_delete_vector(supabase_instance, mock_collection):
    vector_id = "id1"
    supabase_instance.delete(vector_id=vector_id)
    mock_collection.delete.assert_called_once_with([("id1",)])


def test_update_vector(supabase_instance, mock_collection):
    vector_id = "id1"
    new_vector = [0.7, 0.8, 0.9]
    new_payload = {"name": "updated_vector"}

    supabase_instance.update(vector_id=vector_id, vector=new_vector, payload=new_payload)
    mock_collection.upsert.assert_called_once_with([("id1", new_vector, new_payload)])


def test_get_vector(supabase_instance, mock_collection):
    # Create a Mock object to represent the record
    mock_record = Mock()
    mock_record.id = "id1"
    mock_record.metadata = {"name": "vector1"}
    mock_record.values = [0.1, 0.2, 0.3]

    # Set the fetch return value to a list containing our mock record
    mock_collection.fetch.return_value = [mock_record]

    result = supabase_instance.get(vector_id="id1")

    mock_collection.fetch.assert_called_once_with([("id1",)])
    assert result.id == "id1"
    assert result.payload == {"name": "vector1"}


def test_list_vectors(supabase_instance, mock_collection):
    mock_query_results = [("id1", 0.9, {}), ("id2", 0.8, {})]
    mock_fetch_results = [("id1", [0.1, 0.2, 0.3], {"name": "vector1"}), ("id2", [0.4, 0.5, 0.6], {"name": "vector2"})]

    mock_collection.query.return_value = mock_query_results
    mock_collection.fetch.return_value = mock_fetch_results

    results = supabase_instance.list(limit=2, filters={"category": "test"})

    assert len(results[0]) == 2
    assert results[0][0].id == "id1"
    assert results[0][0].payload == {"name": "vector1"}
    assert results[0][1].id == "id2"
    assert results[0][1].payload == {"name": "vector2"}


def test_col_info(supabase_instance, mock_collection):
    info = supabase_instance.col_info()

    assert info == {
        "name": "test_collection",
        "count": 100,
        "dimension": 1536,
        "index": {"method": "hnsw", "metric": "cosine_distance"},
    }


def test_preprocess_filters(supabase_instance):
    # Test single filter
    single_filter = {"category": "test"}
    assert supabase_instance._preprocess_filters(single_filter) == {"category": {"$eq": "test"}}

    # Test multiple filters
    multi_filter = {"category": "test", "type": "document"}
    assert supabase_instance._preprocess_filters(multi_filter) == {
        "$and": [{"category": {"$eq": "test"}}, {"type": {"$eq": "document"}}]
    }

    # Test None filters
    assert supabase_instance._preprocess_filters(None) is None
