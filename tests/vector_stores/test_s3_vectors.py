from mem0.configs.vector_stores.s3_vectors import S3VectorsConfig
import pytest
from botocore.exceptions import ClientError

from mem0.memory.main import Memory
from mem0.vector_stores.s3_vectors import S3Vectors

BUCKET_NAME = "test-bucket"
INDEX_NAME = "test-index"
EMBEDDING_DIMS = 1536
REGION = "us-east-1"


@pytest.fixture
def mock_boto_client(mocker):
    """Fixture to mock the boto3 S3Vectors client."""
    mock_client = mocker.MagicMock()
    mocker.patch("boto3.client", return_value=mock_client)
    return mock_client


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


def test_initialization_creates_resources(mock_boto_client):
    """Test that bucket and index are created if they don't exist."""
    not_found_error = ClientError(
        {"Error": {"Code": "NotFoundException"}}, "OperationName"
    )
    mock_boto_client.get_vector_bucket.side_effect = not_found_error
    mock_boto_client.get_index.side_effect = not_found_error

    S3Vectors(
        vector_bucket_name=BUCKET_NAME,
        collection_name=INDEX_NAME,
        embedding_model_dims=EMBEDDING_DIMS,
        region_name=REGION,
    )

    mock_boto_client.create_vector_bucket.assert_called_once_with(
        vectorBucketName=BUCKET_NAME
    )
    mock_boto_client.create_index.assert_called_once_with(
        vectorBucketName=BUCKET_NAME,
        indexName=INDEX_NAME,
        dataType="float32",
        dimension=EMBEDDING_DIMS,
        distanceMetric="cosine",
    )


def test_initialization_uses_existing_resources(mock_boto_client):
    """Test that existing bucket and index are used if found."""
    mock_boto_client.get_vector_bucket.return_value = {}
    mock_boto_client.get_index.return_value = {}

    S3Vectors(
        vector_bucket_name=BUCKET_NAME,
        collection_name=INDEX_NAME,
        embedding_model_dims=EMBEDDING_DIMS,
        region_name=REGION,
    )

    mock_boto_client.create_vector_bucket.assert_not_called()
    mock_boto_client.create_index.assert_not_called()


def test_memory_initialization_with_config(mock_boto_client, mock_llm, mock_embedder):
    """Test Memory initialization with S3Vectors from config."""

    # check that Attribute error is not raised
    mock_boto_client.get_vector_bucket.return_value = {}
    mock_boto_client.get_index.return_value = {}

    config = {
        "vector_store": {
            "provider": "s3_vectors",
            "config": {
                "vector_bucket_name": BUCKET_NAME,
                "collection_name": INDEX_NAME,
                "embedding_model_dims": EMBEDDING_DIMS,
                "distance_metric": "cosine",
                "region_name": REGION,
            },
        }
    }

    try:
        memory = Memory.from_config(config)

        assert memory.vector_store is not None
        assert isinstance(memory.vector_store, S3Vectors)
        assert isinstance(memory.config.vector_store.config, S3VectorsConfig)
    except AttributeError:
        pytest.fail("Memory initialization failed")


def test_insert(mock_boto_client):
    """Test inserting vectors."""
    store = S3Vectors(
        vector_bucket_name=BUCKET_NAME,
        collection_name=INDEX_NAME,
        embedding_model_dims=EMBEDDING_DIMS,
    )
    vectors = [[0.1, 0.2], [0.3, 0.4]]
    payloads = [{"meta": "data1"}, {"meta": "data2"}]
    ids = ["id1", "id2"]

    store.insert(vectors, payloads, ids)

    mock_boto_client.put_vectors.assert_called_once_with(
        vectorBucketName=BUCKET_NAME,
        indexName=INDEX_NAME,
        vectors=[
            {
                "key": "id1",
                "data": {"float32": [0.1, 0.2]},
                "metadata": {"meta": "data1"},
            },
            {
                "key": "id2",
                "data": {"float32": [0.3, 0.4]},
                "metadata": {"meta": "data2"},
            },
        ],
    )


def test_search(mock_boto_client):
    """Test searching for vectors."""
    mock_boto_client.query_vectors.return_value = {
        "vectors": [{"key": "id1", "distance": 0.9, "metadata": {"meta": "data1"}}]
    }
    store = S3Vectors(
        vector_bucket_name=BUCKET_NAME,
        collection_name=INDEX_NAME,
        embedding_model_dims=EMBEDDING_DIMS,
    )
    query_vector = [0.1, 0.2]
    results = store.search(query="test", vectors=query_vector, limit=1)

    mock_boto_client.query_vectors.assert_called_once()
    assert len(results) == 1
    assert results[0].id == "id1"
    assert results[0].score == 0.9


def test_get(mock_boto_client):
    """Test retrieving a vector by ID."""
    mock_boto_client.get_vectors.return_value = {
        "vectors": [{"key": "id1", "metadata": {"meta": "data1"}}]
    }
    store = S3Vectors(
        vector_bucket_name=BUCKET_NAME,
        collection_name=INDEX_NAME,
        embedding_model_dims=EMBEDDING_DIMS,
    )
    result = store.get("id1")

    mock_boto_client.get_vectors.assert_called_once_with(
        vectorBucketName=BUCKET_NAME,
        indexName=INDEX_NAME,
        keys=["id1"],
        returnData=False,
        returnMetadata=True,
    )
    assert result.id == "id1"
    assert result.payload["meta"] == "data1"


def test_delete(mock_boto_client):
    """Test deleting a vector."""
    store = S3Vectors(
        vector_bucket_name=BUCKET_NAME,
        collection_name=INDEX_NAME,
        embedding_model_dims=EMBEDDING_DIMS,
    )
    store.delete("id1")

    mock_boto_client.delete_vectors.assert_called_once_with(
        vectorBucketName=BUCKET_NAME, indexName=INDEX_NAME, keys=["id1"]
    )


def test_reset(mock_boto_client):
    """Test resetting the vector index."""
    # GIVEN: The index does not exist, so it gets created on init and reset
    not_found_error = ClientError(
        {"Error": {"Code": "NotFoundException"}}, "OperationName"
    )
    mock_boto_client.get_index.side_effect = not_found_error

    # WHEN: The store is initialized
    store = S3Vectors(
        vector_bucket_name=BUCKET_NAME,
        collection_name=INDEX_NAME,
        embedding_model_dims=EMBEDDING_DIMS,
    )

    # THEN: The index is created once during initialization
    assert mock_boto_client.create_index.call_count == 1

    # WHEN: The store is reset
    store.reset()

    # THEN: The index is deleted and then created again
    mock_boto_client.delete_index.assert_called_once_with(
        vectorBucketName=BUCKET_NAME, indexName=INDEX_NAME
    )
    assert mock_boto_client.create_index.call_count == 2
