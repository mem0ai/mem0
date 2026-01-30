from mem0.configs.vector_stores.tos_vectors import TOSVectorsConfig
import pytest
from unittest.mock import MagicMock

from mem0.memory.main import Memory
from mem0.vector_stores.tos_vectors import TOSVectors

BUCKET_NAME = "test-bucket"
INDEX_NAME = "test-index"
EMBEDDING_DIMS = 1536
REGION = "cn-beijing"
ENDPOINT = "https://tosvectors-cn-beijing.volces.com"


@pytest.fixture
def mock_tos_client(mocker):
    """Fixture to mock the TOS VectorClient."""
    mock_client = mocker.MagicMock()
    mocker.patch("tos.VectorClient", return_value=mock_client)
    return mock_client


@pytest.fixture
def mock_env_vars(mocker):
    """Fixture to mock environment variables."""
    mocker.patch("os.getenv", side_effect=lambda key: {
        "TOS_ACCESS_KEY": "test-ak",
        "TOS_SECRET_KEY": "test-sk",
        "TOS_ACCOUNT_ID": "test-account-id"
    }.get(key))


@pytest.fixture
def mock_embedder(mocker):
    mock_embedder = mocker.MagicMock()
    mock_embedder.return_value.embed.return_value = [0.1, 0.2, 0.3]
    mocker.patch("mem0.utils.factory.EmbedderFactory.create", mock_embedder)
    return mock_embedder


@pytest.fixture
def mock_llm(mocker):
    mock_llm = mocker.MagicMock()
    mocker.patch("mem0.utils.factory.LlmFactory.create", mock_llm)
    mocker.patch("mem0.memory.storage.SQLiteManager", mocker.MagicMock())
    return mock_llm


def test_initialization_creates_resources(mock_tos_client, mock_env_vars, mocker):
    """Test that bucket and index are created if they don't exist."""
    import tos

    # Mock TosServerError
    not_found_error = tos.exceptions.TosServerError(
        message="Not Found",
        code="NotFoundException",
        request_id="test-request-id",
        status_code=404
    )
    mock_tos_client.get_vector_bucket.side_effect = not_found_error
    mock_tos_client.get_index.side_effect = not_found_error

    TOSVectors(
        vector_bucket_name=BUCKET_NAME,
        collection_name=INDEX_NAME,
        embedding_model_dims=EMBEDDING_DIMS,
        endpoint=ENDPOINT,
        region=REGION,
    )

    mock_tos_client.create_vector_bucket.assert_called_once_with(BUCKET_NAME)
    mock_tos_client.create_index.assert_called_once()


def test_initialization_uses_existing_resources(mock_tos_client, mock_env_vars):
    """Test that existing bucket and index are used if found."""
    mock_tos_client.get_vector_bucket.return_value = MagicMock()
    mock_tos_client.get_index.return_value = MagicMock()

    TOSVectors(
        vector_bucket_name=BUCKET_NAME,
        collection_name=INDEX_NAME,
        embedding_model_dims=EMBEDDING_DIMS,
        endpoint=ENDPOINT,
        region=REGION,
    )

    mock_tos_client.create_vector_bucket.assert_not_called()
    mock_tos_client.create_index.assert_not_called()


def test_memory_initialization_with_config(mock_tos_client, mock_llm, mock_embedder, mock_env_vars):
    """Test Memory initialization with TOSVectors from config."""
    mock_tos_client.get_vector_bucket.return_value = MagicMock()
    mock_tos_client.get_index.return_value = MagicMock()

    config = {
        "vector_store": {
            "provider": "tos_vectors",
            "config": {
                "vector_bucket_name": BUCKET_NAME,
                "collection_name": INDEX_NAME,
                "embedding_model_dims": EMBEDDING_DIMS,
                "distance_metric": "cosine",
                "endpoint": ENDPOINT,
                "region": REGION,
            },
        }
    }

    try:
        memory = Memory.from_config(config)
        assert memory.vector_store is not None
        assert isinstance(memory.vector_store, TOSVectors)
        assert isinstance(memory.config.vector_store.config, TOSVectorsConfig)
    except AttributeError:
        pytest.fail("Memory initialization failed")


def test_insert(mock_tos_client, mock_env_vars):
    """Test inserting vectors."""
    mock_tos_client.get_vector_bucket.return_value = MagicMock()
    mock_tos_client.get_index.return_value = MagicMock()

    store = TOSVectors(
        vector_bucket_name=BUCKET_NAME,
        collection_name=INDEX_NAME,
        embedding_model_dims=EMBEDDING_DIMS,
        endpoint=ENDPOINT,
    )
    vectors = [[0.1, 0.2], [0.3, 0.4]]
    payloads = [{"meta": "data1"}, {"meta": "data2"}]
    ids = ["id1", "id2"]

    store.insert(vectors, payloads, ids)

    mock_tos_client.put_vectors.assert_called_once()
    call_args = mock_tos_client.put_vectors.call_args
    assert call_args.kwargs["vector_bucket_name"] == BUCKET_NAME
    assert call_args.kwargs["index_name"] == INDEX_NAME
    assert len(call_args.kwargs["vectors"]) == 2


def test_search(mock_tos_client, mock_env_vars):
    """Test searching for vectors."""
    mock_tos_client.get_vector_bucket.return_value = MagicMock()
    mock_tos_client.get_index.return_value = MagicMock()

    # Mock search response
    mock_vector = MagicMock()
    mock_vector.key = "id1"
    mock_vector.distance = 0.9
    mock_vector.metadata = {"meta": "data1"}

    mock_response = MagicMock()
    mock_response.vectors = [mock_vector]
    mock_tos_client.query_vectors.return_value = mock_response

    store = TOSVectors(
        vector_bucket_name=BUCKET_NAME,
        collection_name=INDEX_NAME,
        embedding_model_dims=EMBEDDING_DIMS,
        endpoint=ENDPOINT,
    )
    query_vector = [0.1, 0.2]
    results = store.search(query="test", vectors=query_vector, limit=1)

    mock_tos_client.query_vectors.assert_called_once()
    assert len(results) == 1
    assert results[0].id == "id1"
    assert results[0].score == 0.9


def test_get(mock_tos_client, mock_env_vars):
    """Test retrieving a vector by ID."""
    mock_tos_client.get_vector_bucket.return_value = MagicMock()
    mock_tos_client.get_index.return_value = MagicMock()

    # Mock get response
    mock_vector = MagicMock()
    mock_vector.key = "id1"
    mock_vector.metadata = {"meta": "data1"}

    mock_response = MagicMock()
    mock_response.vectors = [mock_vector]
    mock_tos_client.get_vectors.return_value = mock_response

    store = TOSVectors(
        vector_bucket_name=BUCKET_NAME,
        collection_name=INDEX_NAME,
        embedding_model_dims=EMBEDDING_DIMS,
        endpoint=ENDPOINT,
    )
    result = store.get("id1")

    mock_tos_client.get_vectors.assert_called_once()
    assert result.id == "id1"
    assert result.payload["meta"] == "data1"


def test_delete(mock_tos_client, mock_env_vars):
    """Test deleting a vector."""
    mock_tos_client.get_vector_bucket.return_value = MagicMock()
    mock_tos_client.get_index.return_value = MagicMock()

    store = TOSVectors(
        vector_bucket_name=BUCKET_NAME,
        collection_name=INDEX_NAME,
        embedding_model_dims=EMBEDDING_DIMS,
        endpoint=ENDPOINT,
    )
    store.delete("id1")

    mock_tos_client.delete_vectors.assert_called_once()
    call_args = mock_tos_client.delete_vectors.call_args
    assert call_args.kwargs["vector_bucket_name"] == BUCKET_NAME
    assert call_args.kwargs["index_name"] == INDEX_NAME
    assert call_args.kwargs["keys"] == ["id1"]


def test_reset(mock_tos_client, mock_env_vars):
    """Test resetting the vector index."""
    import tos

    # Mock NotFoundException for initial get_index calls
    not_found_error = tos.exceptions.TosServerError(
        message="Not Found",
        code="NotFoundException",
        request_id="test-request-id",
        status_code=404
    )
    mock_tos_client.get_index.side_effect = not_found_error
    mock_tos_client.get_vector_bucket.return_value = MagicMock()

    # Initialize store
    store = TOSVectors(
        vector_bucket_name=BUCKET_NAME,
        collection_name=INDEX_NAME,
        embedding_model_dims=EMBEDDING_DIMS,
        endpoint=ENDPOINT,
    )

    # Index is created once during initialization
    assert mock_tos_client.create_index.call_count == 1

    # Reset the store
    store.reset()

    # Index should be deleted and created again
    mock_tos_client.delete_index.assert_called_once()
    assert mock_tos_client.create_index.call_count == 2
