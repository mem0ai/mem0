from unittest.mock import MagicMock

import pytest

from mem0.vector_stores.pinecone import PineconeDB


@pytest.fixture
def mock_pinecone_client():
    client = MagicMock()
    client.Index.return_value = MagicMock()
    client.list_indexes.return_value.names.return_value = []
    return client


@pytest.fixture
def pinecone_db(mock_pinecone_client):
    return PineconeDB(
        collection_name="test_index",
        embedding_model_dims=128,
        client=mock_pinecone_client,
        api_key="fake_api_key",
        environment="us-west1-gcp",
        serverless_config=None,
        pod_config=None,
        hybrid_search=False,
        metric="cosine",
        batch_size=100,
        extra_params=None,
        namespace="test_namespace",
    )


def test_create_col_existing_index(mock_pinecone_client):
    # Set up the mock before creating the PineconeDB object
    mock_pinecone_client.list_indexes.return_value.names.return_value = ["test_index"]

    pinecone_db = PineconeDB(
        collection_name="test_index",
        embedding_model_dims=128,
        client=mock_pinecone_client,
        api_key="fake_api_key",
        environment="us-west1-gcp",
        serverless_config=None,
        pod_config=None,
        hybrid_search=False,
        metric="cosine",
        batch_size=100,
        extra_params=None,
        namespace="test_namespace",
    )

    # Reset the mock to verify it wasn't called during the test
    mock_pinecone_client.create_index.reset_mock()

    pinecone_db.create_col(128, "cosine")

    mock_pinecone_client.create_index.assert_not_called()


def test_create_col_new_index(pinecone_db, mock_pinecone_client):
    mock_pinecone_client.list_indexes.return_value.names.return_value = []
    pinecone_db.create_col(128, "cosine")
    mock_pinecone_client.create_index.assert_called()


def test_insert_vectors(pinecone_db):
    vectors = [[0.1] * 128, [0.2] * 128]
    payloads = [{"name": "vector1"}, {"name": "vector2"}]
    ids = ["id1", "id2"]
    pinecone_db.insert(vectors, payloads, ids)
    pinecone_db.index.upsert.assert_called_with(
        vectors=[
            {"id": "id1", "values": [0.1] * 128, "metadata": {"name": "vector1"}},
            {"id": "id2", "values": [0.2] * 128, "metadata": {"name": "vector2"}},
        ],
        namespace="test_namespace",
    )


def test_search_vectors(pinecone_db):
    pinecone_db.index.query.return_value.matches = [{"id": "id1", "score": 0.9, "metadata": {"name": "vector1"}}]
    results = pinecone_db.search("test query", [0.1] * 128, limit=1)
    pinecone_db.index.query.assert_called_with(
        vector=[0.1] * 128,
        top_k=1,
        include_metadata=True,
        include_values=False,
        namespace="test_namespace",
    )
    assert len(results) == 1
    assert results[0].id == "id1"
    assert results[0].score == 0.9


def test_update_vector(pinecone_db):
    pinecone_db.update("id1", vector=[0.5] * 128, payload={"name": "updated"})
    pinecone_db.index.upsert.assert_called_with(
        vectors=[{"id": "id1", "values": [0.5] * 128, "metadata": {"name": "updated"}}],
        namespace="test_namespace",
    )


def test_get_vector_found(pinecone_db):
    # Looking at the _parse_output method, it expects a Vector object
    # or a list of dictionaries, not a dictionary with an 'id' field

    # Create a mock Vector object
    from pinecone import Vector

    mock_vector = Vector(id="id1", values=[0.1] * 128, metadata={"name": "vector1"})

    # Mock the fetch method to return the mock response object
    mock_response = MagicMock()
    mock_response.vectors = {"id1": mock_vector}
    pinecone_db.index.fetch.return_value = mock_response

    result = pinecone_db.get("id1")
    pinecone_db.index.fetch.assert_called_with(ids=["id1"], namespace="test_namespace")
    assert result is not None
    assert result.id == "id1"
    assert result.payload == {"name": "vector1"}


def test_delete_vector(pinecone_db):
    pinecone_db.delete("id1")
    pinecone_db.index.delete.assert_called_with(ids=["id1"], namespace="test_namespace")


def test_get_vector_not_found(pinecone_db):
    pinecone_db.index.fetch.return_value.vectors = {}
    result = pinecone_db.get("id1")
    pinecone_db.index.fetch.assert_called_with(ids=["id1"], namespace="test_namespace")
    assert result is None


def test_list_cols(pinecone_db):
    pinecone_db.list_cols()
    pinecone_db.client.list_indexes.assert_called()


def test_delete_col(pinecone_db):
    pinecone_db.delete_col()
    pinecone_db.client.delete_index.assert_called_with("test_index")


def test_col_info(pinecone_db):
    pinecone_db.col_info()
    pinecone_db.client.describe_index.assert_called_with("test_index")


def test_count_with_namespace(pinecone_db):
    stats_mock = MagicMock()
    stats_mock.namespaces = {"test_namespace": MagicMock(vector_count=10)}
    pinecone_db.index.describe_index_stats.return_value = stats_mock

    count = pinecone_db.count()
    assert count == 10
    pinecone_db.index.describe_index_stats.assert_called_once()


def test_count_without_namespace(pinecone_db):
    pinecone_db.namespace = None
    stats_mock = MagicMock()
    stats_mock.total_vector_count = 20
    pinecone_db.index.describe_index_stats.return_value = stats_mock

    count = pinecone_db.count()
    assert count == 20
    pinecone_db.index.describe_index_stats.assert_called_once()


def test_count_with_non_existent_namespace(pinecone_db):
    stats_mock = MagicMock()
    stats_mock.namespaces = {"another_namespace": MagicMock(vector_count=5)}
    pinecone_db.index.describe_index_stats.return_value = stats_mock

    count = pinecone_db.count()
    assert count == 0
    pinecone_db.index.describe_index_stats.assert_called_once()


def test_count_with_none_vector_count(pinecone_db):
    stats_mock = MagicMock()
    stats_mock.namespaces = {"test_namespace": MagicMock(vector_count=None)}
    pinecone_db.index.describe_index_stats.return_value = stats_mock

    count = pinecone_db.count()
    assert count == 0
    pinecone_db.index.describe_index_stats.assert_called_once()
