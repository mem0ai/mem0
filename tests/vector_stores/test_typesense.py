import pytest
from unittest.mock import Mock, patch

from mem0.vector_stores.typesense import TypesenseDB, OutputData


@pytest.fixture
def mock_client():
    """Create a mock Typesense client."""
    client = Mock()
    client.collections = Mock()
    client.collections.retrieve = Mock(return_value=[])
    client.collections.create = Mock()
    client.collections.delete = Mock()
    return client


@pytest.fixture
def mock_collection():
    """Create a mock Typesense collection."""
    collection = Mock()
    collection.documents = Mock()
    collection.documents.create_many = Mock()
    collection.documents.search = Mock()
    collection.documents.delete = Mock()
    collection.documents.update = Mock()
    collection.documents.retrieve = Mock()
    collection.retrieve = Mock()
    return collection


@pytest.fixture
def typesense_instance(mock_client, mock_collection):
    """Create a TypesenseDB instance with mocked client."""
    with patch('mem0.vector_stores.typesense.typesense') as mock_typesense:
        mock_typesense.Client.return_value = mock_client
        
        instance = TypesenseDB(
            host="localhost",
            port=8108,
            protocol="http",
            api_key="test_key",
            collection_name="test_collection",
            embedding_model_dims=128,
        )
        instance.client = mock_client
        instance.client.collections = Mock()
        instance.client.collections.retrieve = Mock(return_value=[])
        instance.client.collections.create = Mock()
        instance.client.collections.delete = Mock()
        
        # Setup proper mocking for collection access
        collection_mock = Mock()
        collection_mock.documents = Mock()
        collection_mock.documents.create_many = Mock()
        collection_mock.documents.search = Mock()
        collection_mock.documents.delete = Mock()
        collection_mock.documents.update = Mock()
        collection_mock.documents.retrieve = Mock()
        collection_mock.retrieve = Mock()
        
        # Mock document access by ID
        document_mock = Mock()
        document_mock.delete = Mock()
        document_mock.update = Mock()
        document_mock.retrieve = Mock()
        collection_mock.documents.__getitem__ = Mock(return_value=document_mock)
        
        instance.client.collections.__getitem__ = Mock(return_value=collection_mock)
        return instance


def test_typesense_init(mock_client):
    """Test TypesenseDB initialization."""
    with patch('mem0.vector_stores.typesense.typesense') as mock_typesense:
        mock_typesense.Client.return_value = mock_client

        instance = TypesenseDB(
            host="localhost",
            port=8108,
            protocol="http",
            api_key="test_key",
            collection_name="test_collection",
            embedding_model_dims=128,
        )

        assert instance.host == "localhost"
        assert instance.port == 8108
        assert instance.protocol == "http"
        assert instance.api_key == "test_key"
        assert instance.collection_name == "test_collection"
        assert instance.embedding_model_dims == 128


def test_create_col(typesense_instance):
    """Test collection creation."""
    typesense_instance.create_col(name="new_collection", vector_size=256)

    # Verify that create was called
    assert typesense_instance.client.collections.create.called


def test_insert(typesense_instance):
    """Test vector insertion."""
    vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    payloads = [{"text": "test1"}, {"text": "test2"}]
    ids = ["id1", "id2"]

    typesense_instance.insert(vectors=vectors, payloads=payloads, ids=ids)

    assert typesense_instance.client.collections.__getitem__.return_value.documents.create_many.called


def test_search(typesense_instance):
    """Test vector search."""
    # Mock the search results
    mock_results = {
        'hits': [
            {
                'document': {'id': 'id1', 'payload': '{"text": "test1"}'},
                'vector_distance': 0.2
            },
            {
                'document': {'id': 'id2', 'payload': '{"text": "test2"}'},
                'vector_distance': 0.3
            }
        ]
    }
    
    typesense_instance.client.collections.__getitem__.return_value.documents.search.return_value = mock_results

    query_vector = [0.2, 0.3, 0.4]
    results = typesense_instance.search(query="test", vectors=query_vector, limit=5)

    assert isinstance(results, list)
    assert len(results) <= 5
    assert typesense_instance.client.collections.__getitem__.return_value.documents.search.called


def test_delete(typesense_instance):
    """Test vector deletion."""
    typesense_instance.delete(vector_id="test_id")

    # Access the mocked document delete method
    collection = typesense_instance.client.collections.__getitem__.return_value
    document = collection.documents.__getitem__.return_value
    assert document.delete.called


def test_update(typesense_instance):
    """Test vector update."""
    new_vector = [0.7, 0.8, 0.9]
    new_payload = {"text": "updated"}

    # Mock existing document
    collection = typesense_instance.client.collections.__getitem__.return_value
    document = collection.documents.__getitem__.return_value
    document.retrieve.return_value = {
        'id': 'test_id',
        'payload': '{"text": "old"}'
    }

    typesense_instance.update(vector_id="test_id", vector=new_vector, payload=new_payload)

    assert document.update.called


def test_get(typesense_instance):
    """Test retrieving a vector by ID."""
    # Mock the document retrieval
    mock_document = {
        'id': 'test_id',
        'payload': '{"text": "test"}'
    }
    collection = typesense_instance.client.collections.__getitem__.return_value
    document = collection.documents.__getitem__.return_value
    document.retrieve.return_value = mock_document

    result = typesense_instance.get(vector_id="test_id")

    assert result is not None
    assert isinstance(result, OutputData)
    assert result.id == "test_id"


def test_list_cols(typesense_instance):
    """Test listing collections."""
    typesense_instance.client.collections.retrieve.return_value = [
        {"name": "collection1"},
        {"name": "collection2"}
    ]

    collections = typesense_instance.list_cols()

    assert isinstance(collections, list)
    assert len(collections) == 2
    assert "collection1" in collections


def test_delete_col(typesense_instance):
    """Test collection deletion."""
    typesense_instance.delete_col()

    assert typesense_instance.client.collections.__getitem__.return_value.delete.called


def test_col_info(typesense_instance):
    """Test getting collection information."""
    # Mock collection info
    mock_collection_info = {
        'name': 'test_collection',
        'num_documents': 100
    }
    typesense_instance.client.collections.__getitem__.return_value.retrieve.return_value = mock_collection_info

    info = typesense_instance.col_info()

    assert isinstance(info, dict)
    assert 'name' in info
    assert 'num_documents' in info


def test_list(typesense_instance):
    """Test listing vectors."""
    # Mock the search results
    mock_results = {
        'hits': [
            {
                'document': {'id': 'id1', 'payload': '{"text": "test1"}'}
            }
        ]
    }
    typesense_instance.client.collections.__getitem__.return_value.documents.search.return_value = mock_results

    results = typesense_instance.list(limit=10)

    assert isinstance(results, list)
    assert len(results) > 0


def test_reset(typesense_instance):
    """Test resetting the collection."""
    typesense_instance.reset()

    assert typesense_instance.client.collections.__getitem__.return_value.delete.called


def test_search_with_filters(typesense_instance):
    """Test vector search with filters."""
    # Mock the search results
    mock_results = {
        'hits': [
            {
                'document': {'id': 'id1', 'payload': '{"text": "test1", "category": "A"}'},
                'vector_distance': 0.2
            }
        ]
    }
    
    typesense_instance.client.collections.__getitem__.return_value.documents.search.return_value = mock_results

    query_vector = [0.2, 0.3, 0.4]
    results = typesense_instance.search(
        query="test",
        vectors=query_vector,
        limit=5,
        filters={"category": "A"}
    )

    assert isinstance(results, list)
    # Should only return filtered results
    for result in results:
        assert result.payload.get("category") == "A"


def test_output_data_model():
    """Test OutputData model."""
    data = OutputData(
        id="test_id",
        score=0.95,
        payload={"text": "test"}
    )

    assert data.id == "test_id"
    assert data.score == 0.95
    assert data.payload == {"text": "test"}


def test_insert_without_ids(typesense_instance):
    """Test vector insertion without providing IDs."""
    vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    payloads = [{"text": "test1"}, {"text": "test2"}]

    typesense_instance.insert(vectors=vectors, payloads=payloads)

    assert typesense_instance.client.collections.__getitem__.return_value.documents.create_many.called


def test_insert_without_payloads(typesense_instance):
    """Test vector insertion without providing payloads."""
    vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    ids = ["id1", "id2"]

    typesense_instance.insert(vectors=vectors, ids=ids)

    assert typesense_instance.client.collections.__getitem__.return_value.documents.create_many.called


def test_get_nonexistent_vector(typesense_instance):
    """Test getting a non-existent vector."""
    # Mock exception for non-existent document
    collection = typesense_instance.client.collections.__getitem__.return_value
    document = collection.documents.__getitem__.return_value
    document.retrieve.side_effect = Exception("Document not found")

    result = typesense_instance.get(vector_id="nonexistent")

    assert result is None


def test_update_nonexistent_vector(typesense_instance):
    """Test updating a non-existent vector."""
    # Mock exception for non-existent document
    collection = typesense_instance.client.collections.__getitem__.return_value
    document = collection.documents.__getitem__.return_value
    document.retrieve.side_effect = Exception("Document not found")

    typesense_instance.update(vector_id="nonexistent", vector=[0.1, 0.2, 0.3])

    # Should not call update for non-existent vector
    assert not document.update.called


def test_list_with_filters(typesense_instance):
    """Test listing vectors with filters."""
    # Mock the search results
    mock_results = {
        'hits': [
            {
                'document': {'id': 'id1', 'payload': '{"text": "test1", "category": "A"}'}
            }
        ]
    }
    typesense_instance.client.collections.__getitem__.return_value.documents.search.return_value = mock_results

    results = typesense_instance.list(filters={"category": "A"}, limit=10)

    assert isinstance(results, list)
    assert len(results) > 0
    # Should only return filtered results
    for result in results[0]:
        assert result.payload.get("category") == "A"
