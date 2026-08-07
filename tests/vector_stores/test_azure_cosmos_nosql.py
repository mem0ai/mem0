from unittest.mock import MagicMock, patch

import pytest
from azure.cosmos.exceptions import CosmosResourceNotFoundError

from mem0.vector_stores.azure_cosmos_nosql import AzureCosmosNoSQL


@pytest.fixture
def mock_cosmos_client():
    client = MagicMock()
    database = MagicMock()
    container = MagicMock()
    client.create_database_if_not_exists.return_value = database
    database.create_container_if_not_exists.return_value = container
    return client


@pytest.fixture
def cosmos_db(mock_cosmos_client):
    return AzureCosmosNoSQL(
        collection_name="mem0",
        database_name="mem0db",
        embedding_model_dims=128,
        client=mock_cosmos_client,
        metric="cosine",
        index_type="diskANN",
    )


def test_init_requires_credentials(monkeypatch):
    monkeypatch.delenv("AZURE_COSMOS_CONNECTION_STRING", raising=False)
    monkeypatch.delenv("AZURE_COSMOS_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_COSMOS_KEY", raising=False)
    with pytest.raises(ValueError, match="credentials"):
        AzureCosmosNoSQL(
            collection_name="mem0",
            database_name="mem0db",
            embedding_model_dims=128,
        )


def test_init_with_connection_string(monkeypatch):
    monkeypatch.delenv("AZURE_COSMOS_CONNECTION_STRING", raising=False)
    with patch("mem0.vector_stores.azure_cosmos_nosql.CosmosClient") as mock_client_cls:
        AzureCosmosNoSQL(
            collection_name="mem0",
            database_name="mem0db",
            embedding_model_dims=128,
            connection_string="AccountEndpoint=https://x.documents.azure.com:443/;AccountKey=abc==;",
        )
        mock_client_cls.from_connection_string.assert_called_once()


def test_init_with_endpoint_and_key(monkeypatch):
    monkeypatch.delenv("AZURE_COSMOS_CONNECTION_STRING", raising=False)
    with patch("mem0.vector_stores.azure_cosmos_nosql.CosmosClient") as mock_client_cls:
        AzureCosmosNoSQL(
            collection_name="mem0",
            database_name="mem0db",
            embedding_model_dims=128,
            endpoint="https://x.documents.azure.com:443/",
            api_key="fake_key",
        )
        mock_client_cls.assert_called_once_with(url="https://x.documents.azure.com:443/", credential="fake_key")


def test_create_col_policies(cosmos_db, mock_cosmos_client):
    mock_cosmos_client.create_database_if_not_exists.assert_called_with(id="mem0db")
    database = mock_cosmos_client.create_database_if_not_exists.return_value
    _, kwargs = database.create_container_if_not_exists.call_args

    assert kwargs["id"] == "mem0"
    embedding = kwargs["vector_embedding_policy"]["vectorEmbeddings"][0]
    assert embedding["path"] == "/vector"
    assert embedding["dimensions"] == 128
    assert embedding["distanceFunction"] == "cosine"
    vector_index = kwargs["indexing_policy"]["vectorIndexes"][0]
    assert vector_index == {"path": "/vector", "type": "diskANN"}
    assert {"path": "/vector/*"} in kwargs["indexing_policy"]["excludedPaths"]


def test_insert_vectors(cosmos_db):
    vectors = [[0.1] * 128, [0.2] * 128]
    payloads = [{"name": "vector1"}, {"name": "vector2"}]
    ids = ["id1", "id2"]

    cosmos_db.insert(vectors, payloads, ids)

    assert cosmos_db.container.upsert_item.call_count == 2
    cosmos_db.container.upsert_item.assert_any_call(
        {"id": "id1", "vector": [0.1] * 128, "payload": {"name": "vector1"}}
    )
    cosmos_db.container.upsert_item.assert_any_call(
        {"id": "id2", "vector": [0.2] * 128, "payload": {"name": "vector2"}}
    )


def test_search_returns_similarity_scores(cosmos_db):
    cosmos_db.container.query_items.return_value = [
        {"id": "id1", "payload": {"name": "vector1"}, "distance": 0.9},
        {"id": "id2", "payload": {"name": "vector2"}, "distance": -0.2},
    ]

    results = cosmos_db.search("test query", [0.1] * 128, top_k=2)

    _, kwargs = cosmos_db.container.query_items.call_args
    assert "VectorDistance(c.vector, @embedding, false, {'distanceFunction': 'cosine'" in kwargs["query"]
    assert "ORDER BY VectorDistance" in kwargs["query"]
    assert {"name": "@top_k", "value": 2} in kwargs["parameters"]
    assert {"name": "@embedding", "value": [0.1] * 128} in kwargs["parameters"]

    assert len(results) == 2
    assert results[0].id == "id1"
    assert results[0].score == 0.9  # cosine similarity passed through
    assert results[0].payload == {"name": "vector1"}
    assert results[1].score == 0.0  # negative cosine similarity clamped to 0


def test_search_euclidean_distance_conversion(mock_cosmos_client):
    db = AzureCosmosNoSQL(
        collection_name="mem0",
        database_name="mem0db",
        embedding_model_dims=128,
        client=mock_cosmos_client,
        metric="euclidean",
    )
    db.container.query_items.return_value = [{"id": "id1", "payload": {}, "distance": 1.0}]

    results = db.search("test query", [0.1] * 128, top_k=1)

    _, kwargs = db.container.query_items.call_args
    assert "{'distanceFunction': 'euclidean'" in kwargs["query"]
    assert results[0].score == 0.5  # 1 / (1 + 1.0)


def test_search_with_filters(cosmos_db):
    cosmos_db.container.query_items.return_value = []

    cosmos_db.search("test query", [0.1] * 128, top_k=5, filters={"user_id": "alice", "agent_id": "bot"})

    _, kwargs = cosmos_db.container.query_items.call_args
    assert 'WHERE c.payload["user_id"] = @p0 AND c.payload["agent_id"] = @p1' in kwargs["query"]
    assert {"name": "@p0", "value": "alice"} in kwargs["parameters"]
    assert {"name": "@p1", "value": "bot"} in kwargs["parameters"]


def test_search_with_range_filter(cosmos_db):
    cosmos_db.container.query_items.return_value = []

    cosmos_db.search("test query", [0.1] * 128, top_k=5, filters={"created_at": {"gte": 1, "lte": 2}})

    _, kwargs = cosmos_db.container.query_items.call_args
    assert 'c.payload["created_at"] >= @p0_gte AND c.payload["created_at"] <= @p0_lte' in kwargs["query"]
    assert {"name": "@p0_gte", "value": 1} in kwargs["parameters"]
    assert {"name": "@p0_lte", "value": 2} in kwargs["parameters"]


def test_search_rejects_invalid_filter_key(cosmos_db):
    with pytest.raises(ValueError, match="Invalid filter key"):
        cosmos_db.search("test query", [0.1] * 128, filters={'bad"] = 1 OR 1=1 --': "x"})


def test_get_vector_found(cosmos_db):
    cosmos_db.container.read_item.return_value = {"id": "id1", "vector": [0.1] * 128, "payload": {"name": "vector1"}}

    result = cosmos_db.get("id1")

    cosmos_db.container.read_item.assert_called_with(item="id1", partition_key="id1")
    assert result.id == "id1"
    assert result.payload == {"name": "vector1"}


def test_get_vector_not_found(cosmos_db):
    cosmos_db.container.read_item.side_effect = CosmosResourceNotFoundError()

    result = cosmos_db.get("missing")

    assert result is None


def test_update_vector_and_payload(cosmos_db):
    cosmos_db.container.read_item.return_value = {"id": "id1", "vector": [0.1] * 128, "payload": {"name": "old"}}

    cosmos_db.update("id1", vector=[0.5] * 128, payload={"name": "new"})

    cosmos_db.container.upsert_item.assert_called_with({"id": "id1", "vector": [0.5] * 128, "payload": {"name": "new"}})


def test_update_payload_only_keeps_vector(cosmos_db):
    cosmos_db.container.read_item.return_value = {"id": "id1", "vector": [0.1] * 128, "payload": {"name": "old"}}

    cosmos_db.update("id1", payload={"name": "new"})

    cosmos_db.container.upsert_item.assert_called_with({"id": "id1", "vector": [0.1] * 128, "payload": {"name": "new"}})


def test_update_missing_vector_is_noop(cosmos_db):
    cosmos_db.container.read_item.side_effect = CosmosResourceNotFoundError()

    cosmos_db.update("missing", payload={"name": "new"})

    cosmos_db.container.upsert_item.assert_not_called()


def test_delete_vector(cosmos_db):
    cosmos_db.delete("id1")

    cosmos_db.container.delete_item.assert_called_with(item="id1", partition_key="id1")


def test_delete_vector_not_found_does_not_raise(cosmos_db):
    cosmos_db.container.delete_item.side_effect = CosmosResourceNotFoundError()

    cosmos_db.delete("missing")


def test_list_with_filters(cosmos_db):
    cosmos_db.container.query_items.return_value = [{"id": "id1", "payload": {"name": "vector1"}}]

    results = cosmos_db.list(filters={"user_id": "alice"}, top_k=10)

    _, kwargs = cosmos_db.container.query_items.call_args
    assert kwargs["query"].startswith("SELECT TOP @top_k c.id, c.payload FROM c WHERE")
    assert "VectorDistance" not in kwargs["query"]
    assert len(results) == 1
    assert results[0][0].id == "id1"


def test_list_cols(cosmos_db):
    cosmos_db.database.list_containers.return_value = [{"id": "mem0"}, {"id": "other"}]

    assert cosmos_db.list_cols() == ["mem0", "other"]


def test_delete_col(cosmos_db):
    cosmos_db.delete_col()

    cosmos_db.database.delete_container.assert_called_with("mem0")


def test_col_info(cosmos_db):
    cosmos_db.col_info()

    cosmos_db.container.read.assert_called_once()


def test_count(cosmos_db):
    cosmos_db.container.query_items.return_value = iter([42])

    assert cosmos_db.count() == 42


def test_reset(cosmos_db, mock_cosmos_client):
    database = mock_cosmos_client.create_database_if_not_exists.return_value
    database.create_container_if_not_exists.reset_mock()

    cosmos_db.reset()

    database.delete_container.assert_called_with("mem0")
    database.create_container_if_not_exists.assert_called_once()
