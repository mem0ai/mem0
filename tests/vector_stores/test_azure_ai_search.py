import json
from unittest.mock import MagicMock, Mock, patch

import pytest
from azure.core.exceptions import HttpResponseError

from mem0.configs.vector_stores.azure_ai_search import AzureAISearchConfig

# Import the AzureAISearch class and related models
from mem0.vector_stores.azure_ai_search import AzureAISearch


# Fixture to patch SearchClient and SearchIndexClient and create an instance of AzureAISearch.
@pytest.fixture
def mock_clients():
    with (
        patch("mem0.vector_stores.azure_ai_search.SearchClient") as MockSearchClient,
        patch("mem0.vector_stores.azure_ai_search.SearchIndexClient") as MockIndexClient,
        patch("mem0.vector_stores.azure_ai_search.AzureKeyCredential") as MockAzureKeyCredential,
    ):
        # Create mocked instances for search and index clients.
        mock_search_client = MockSearchClient.return_value
        mock_index_client = MockIndexClient.return_value

        # Mock the client._client._config.user_agent_policy.add_user_agent
        mock_search_client._client = MagicMock()
        mock_search_client._client._config.user_agent_policy.add_user_agent = Mock()
        mock_index_client._client = MagicMock()
        mock_index_client._client._config.user_agent_policy.add_user_agent = Mock()

        # Stub required methods on search_client.
        mock_search_client.upload_documents = Mock()
        mock_search_client.upload_documents.return_value = [{"status": True, "id": "doc1"}]
        mock_search_client.search = Mock()
        mock_search_client.delete_documents = Mock()
        mock_search_client.delete_documents.return_value = [{"status": True, "id": "doc1"}]
        mock_search_client.merge_or_upload_documents = Mock()
        mock_search_client.merge_or_upload_documents.return_value = [{"status": True, "id": "doc1"}]
        mock_search_client.get_document = Mock()
        mock_search_client.close = Mock()

        # Stub required methods on index_client.
        mock_index_client.create_or_update_index = Mock()
        mock_index_client.list_indexes = Mock()
        mock_index_client.list_index_names = Mock(return_value=[])
        mock_index_client.delete_index = Mock()
        # For col_info() we assume get_index returns an object with name and fields attributes.
        fake_index = Mock()
        fake_index.name = "test-index"
        fake_index.fields = ["id", "vector", "payload", "user_id", "run_id", "agent_id"]
        mock_index_client.get_index = Mock(return_value=fake_index)
        mock_index_client.close = Mock()

        yield mock_search_client, mock_index_client, MockAzureKeyCredential


@pytest.fixture
def azure_ai_search_instance(mock_clients):
    mock_search_client, mock_index_client, _ = mock_clients
    # Create an instance with dummy parameters.
    instance = AzureAISearch(
        service_name="test-service",
        collection_name="test-index",
        api_key="test-api-key",
        embedding_model_dims=3,
        compression_type="binary",  # testing binary quantization option
        use_float16=True,
    )
    # Return instance and clients for verification.
    return instance, mock_search_client, mock_index_client


# --- Tests for AzureAISearchConfig ---


def test_config_validation_valid():
    """Test valid configurations are accepted."""
    # Test minimal configuration
    config = AzureAISearchConfig(service_name="test-service", api_key="test-api-key", embedding_model_dims=768)
    assert config.collection_name == "mem0"  # Default value
    assert config.service_name == "test-service"
    assert config.api_key == "test-api-key"
    assert config.embedding_model_dims == 768
    assert config.compression_type is None
    assert config.use_float16 is False

    # Test with all optional parameters
    config = AzureAISearchConfig(
        collection_name="custom-index",
        service_name="test-service",
        api_key="test-api-key",
        embedding_model_dims=1536,
        compression_type="scalar",
        use_float16=True,
    )
    assert config.collection_name == "custom-index"
    assert config.compression_type == "scalar"
    assert config.use_float16 is True


def test_config_validation_invalid_compression_type():
    """Test that invalid compression types are rejected."""
    with pytest.raises(ValueError) as exc_info:
        AzureAISearchConfig(
            service_name="test-service",
            api_key="test-api-key",
            embedding_model_dims=768,
            compression_type="invalid-type",  # Not a valid option
        )
    assert "Invalid compression_type" in str(exc_info.value)


def test_config_validation_deprecated_use_compression():
    """Test that using the deprecated use_compression parameter raises an error."""
    with pytest.raises(ValueError) as exc_info:
        AzureAISearchConfig(
            service_name="test-service",
            api_key="test-api-key",
            embedding_model_dims=768,
            use_compression=True,  # Deprecated parameter
        )
    # Fix: Use a partial string match instead of exact match
    assert "use_compression" in str(exc_info.value)
    assert "no longer supported" in str(exc_info.value)


def test_config_validation_extra_fields():
    """Test that extra fields are rejected."""
    with pytest.raises(ValueError) as exc_info:
        AzureAISearchConfig(
            service_name="test-service",
            api_key="test-api-key",
            embedding_model_dims=768,
            unknown_parameter="value",  # Extra field
        )
    assert "Extra fields not allowed" in str(exc_info.value)
    assert "unknown_parameter" in str(exc_info.value)


# --- Tests for AzureAISearch initialization ---


def test_initialization(mock_clients):
    """Test AzureAISearch initialization with different parameters."""
    mock_search_client, mock_index_client, mock_azure_key_credential = mock_clients

    # Test with minimal parameters
    instance = AzureAISearch(
        service_name="test-service", collection_name="test-index", api_key="test-api-key", embedding_model_dims=768
    )

    # Verify initialization parameters
    assert instance.index_name == "test-index"
    assert instance.collection_name == "test-index"
    assert instance.embedding_model_dims == 768
    assert instance.compression_type == "none"  # Default when None is passed
    assert instance.use_float16 is False

    # Verify client creation
    mock_azure_key_credential.assert_called_with("test-api-key")
    assert "mem0" in mock_search_client._client._config.user_agent_policy.add_user_agent.call_args[0]
    assert "mem0" in mock_index_client._client._config.user_agent_policy.add_user_agent.call_args[0]

    # Verify index creation was called
    mock_index_client.create_or_update_index.assert_called_once()


def test_initialization_with_compression_types(mock_clients):
    """Test initialization with different compression types."""
    mock_search_client, mock_index_client, _ = mock_clients

    # Test with scalar compression
    instance = AzureAISearch(
        service_name="test-service",
        collection_name="scalar-index",
        api_key="test-api-key",
        embedding_model_dims=768,
        compression_type="scalar",
    )
    assert instance.compression_type == "scalar"

    # Capture the index creation call
    args, _ = mock_index_client.create_or_update_index.call_args_list[-1]
    index = args[0]
    # Verify scalar compression was configured
    assert hasattr(index.vector_search, "compressions")
    assert len(index.vector_search.compressions) > 0
    assert "ScalarQuantizationCompression" in str(type(index.vector_search.compressions[0]))

    # Test with binary compression
    instance = AzureAISearch(
        service_name="test-service",
        collection_name="binary-index",
        api_key="test-api-key",
        embedding_model_dims=768,
        compression_type="binary",
    )
    assert instance.compression_type == "binary"

    # Capture the index creation call
    args, _ = mock_index_client.create_or_update_index.call_args_list[-1]
    index = args[0]
    # Verify binary compression was configured
    assert hasattr(index.vector_search, "compressions")
    assert len(index.vector_search.compressions) > 0
    assert "BinaryQuantizationCompression" in str(type(index.vector_search.compressions[0]))

    # Test with no compression
    instance = AzureAISearch(
        service_name="test-service",
        collection_name="no-compression-index",
        api_key="test-api-key",
        embedding_model_dims=768,
        compression_type=None,
    )
    assert instance.compression_type == "none"

    # Capture the index creation call
    args, _ = mock_index_client.create_or_update_index.call_args_list[-1]
    index = args[0]
    # Verify no compression was configured
    assert hasattr(index.vector_search, "compressions")
    assert len(index.vector_search.compressions) == 0


def test_initialization_with_float_precision(mock_clients):
    """Test initialization with different float precision settings."""
    mock_search_client, mock_index_client, _ = mock_clients

    # Test with half precision (float16)
    instance = AzureAISearch(
        service_name="test-service",
        collection_name="float16-index",
        api_key="test-api-key",
        embedding_model_dims=768,
        use_float16=True,
    )
    assert instance.use_float16 is True

    # Capture the index creation call
    args, _ = mock_index_client.create_or_update_index.call_args_list[-1]
    index = args[0]
    # Find the vector field and check its type
    vector_field = next((f for f in index.fields if f.name == "vector"), None)
    assert vector_field is not None
    assert "Edm.Half" in vector_field.type

    # Test with full precision (float32)
    instance = AzureAISearch(
        service_name="test-service",
        collection_name="float32-index",
        api_key="test-api-key",
        embedding_model_dims=768,
        use_float16=False,
    )
    assert instance.use_float16 is False

    # Capture the index creation call
    args, _ = mock_index_client.create_or_update_index.call_args_list[-1]
    index = args[0]
    # Find the vector field and check its type
    vector_field = next((f for f in index.fields if f.name == "vector"), None)
    assert vector_field is not None
    assert "Edm.Single" in vector_field.type


# --- Tests for create_col method ---


def test_create_col(azure_ai_search_instance):
    """Test the create_col method creates an index with the correct configuration."""
    instance, _, mock_index_client = azure_ai_search_instance

    # create_col is called during initialization, so we check the call that was already made
    mock_index_client.create_or_update_index.assert_called_once()

    # Verify the index configuration
    args, _ = mock_index_client.create_or_update_index.call_args
    index = args[0]

    # Check basic properties
    assert index.name == "test-index"
    assert len(index.fields) == 12  # Updated: now includes all mem0 fields

    # Check that all required fields are present (updated list)
    field_names = [f.name for f in index.fields]
    expected_fields = [
        "id", "user_id", "run_id", "agent_id", "memory", 
        "hash", "metadata", "memory_type", "created_at", 
        "updated_at", "vector", "payload"
    ]
    
    for field in expected_fields:
        assert field in field_names, f"Expected field '{field}' not found in index"

    # Check that id is the key field
    id_field = next(f for f in index.fields if f.name == "id")
    assert id_field.key is True

    # Check vector search configuration
    assert index.vector_search is not None
    assert len(index.vector_search.profiles) == 1
    assert index.vector_search.profiles[0].name == "my-vector-config"
    assert index.vector_search.profiles[0].algorithm_configuration_name == "my-algorithms-config"

    # Check algorithms
    assert len(index.vector_search.algorithms) == 1
    assert index.vector_search.algorithms[0].name == "my-algorithms-config"
    assert "HnswAlgorithmConfiguration" in str(type(index.vector_search.algorithms[0]))

    # With binary compression and float16, we should have compression configuration
    assert len(index.vector_search.compressions) == 1
    assert index.vector_search.compressions[0].compression_name == "myCompression"
    assert "BinaryQuantizationCompression" in str(type(index.vector_search.compressions[0]))


def test_create_col_scalar_compression(mock_clients):
    """Test creating a collection with scalar compression."""
    mock_search_client, mock_index_client, _ = mock_clients

    AzureAISearch(
        service_name="test-service",
        collection_name="scalar-index",
        api_key="test-api-key",
        embedding_model_dims=768,
        compression_type="scalar",
    )

    # Verify the index configuration
    args, _ = mock_index_client.create_or_update_index.call_args
    index = args[0]

    # Check compression configuration
    assert len(index.vector_search.compressions) == 1
    assert index.vector_search.compressions[0].compression_name == "myCompression"
    assert "ScalarQuantizationCompression" in str(type(index.vector_search.compressions[0]))

    # Check profile references compression
    assert index.vector_search.profiles[0].compression_name == "myCompression"


def test_create_col_no_compression(mock_clients):
    """Test creating a collection with no compression."""
    mock_search_client, mock_index_client, _ = mock_clients

    AzureAISearch(
        service_name="test-service",
        collection_name="no-compression-index",
        api_key="test-api-key",
        embedding_model_dims=768,
        compression_type=None,
    )

    # Verify the index configuration
    args, _ = mock_index_client.create_or_update_index.call_args
    index = args[0]

    # Check compression configuration - should be empty
    assert len(index.vector_search.compressions) == 0

    # Check profile doesn't reference compression
    assert index.vector_search.profiles[0].compression_name is None


# --- Tests for insert method ---


def test_insert_single(azure_ai_search_instance):
    """Test inserting a single vector."""
    instance, mock_search_client, _ = azure_ai_search_instance
    vectors = [[0.1, 0.2, 0.3]]
    payloads = [{"user_id": "user1", "run_id": "run1", "agent_id": "agent1"}]
    ids = ["doc1"]

    # Fix: Include status_code: 201 in mock response
    mock_search_client.upload_documents.return_value = [{"status": True, "id": "doc1", "status_code": 201}]

    instance.insert(vectors, payloads, ids)

    # Verify upload_documents was called correctly
    mock_search_client.upload_documents.assert_called_once()
    args, _ = mock_search_client.upload_documents.call_args
    documents = args[0]

    # Verify document structure
    assert len(documents) == 1
    assert documents[0]["id"] == "doc1"
    assert documents[0]["vector"] == [0.1, 0.2, 0.3]
    assert documents[0]["payload"] == json.dumps(payloads[0])
    assert documents[0]["user_id"] == "user1"
    assert documents[0]["run_id"] == "run1"
    assert documents[0]["agent_id"] == "agent1"


def test_insert_multiple(azure_ai_search_instance):
    """Test inserting multiple vectors in one call."""
    instance, mock_search_client, _ = azure_ai_search_instance

    # Create multiple vectors
    num_docs = 3
    vectors = [[float(i) / 10, float(i + 1) / 10, float(i + 2) / 10] for i in range(num_docs)]
    payloads = [{"user_id": f"user{i}", "content": f"Test content {i}"} for i in range(num_docs)]
    ids = [f"doc{i}" for i in range(num_docs)]

    # Configure mock to return success for all documents (fix: add status_code 201)
    mock_search_client.upload_documents.return_value = [
        {"status": True, "id": id_val, "status_code": 201} for id_val in ids
    ]

    # Insert the documents
    instance.insert(vectors, payloads, ids)

    # Verify upload_documents was called with correct documents
    mock_search_client.upload_documents.assert_called_once()
    args, _ = mock_search_client.upload_documents.call_args
    documents = args[0]

    # Verify all documents were included
    assert len(documents) == num_docs

    # Check first document
    assert documents[0]["id"] == "doc0"
    assert documents[0]["vector"] == [0.0, 0.1, 0.2]
    assert documents[0]["payload"] == json.dumps(payloads[0])
    assert documents[0]["user_id"] == "user0"

    # Check last document
    assert documents[2]["id"] == "doc2"
    assert documents[2]["vector"] == [0.2, 0.3, 0.4]
    assert documents[2]["payload"] == json.dumps(payloads[2])
    assert documents[2]["user_id"] == "user2"


def test_insert_with_error(azure_ai_search_instance):
    """Test insert when Azure returns an error for one or more documents."""
    instance, mock_search_client, _ = azure_ai_search_instance

    # Configure mock to return an error for one document
    mock_search_client.upload_documents.return_value = [{"status": False, "id": "doc1", "errorMessage": "Azure error"}]

    vectors = [[0.1, 0.2, 0.3]]
    payloads = [{"user_id": "user1"}]
    ids = ["doc1"]

    # Insert should raise an exception
    with pytest.raises(Exception) as exc_info:
        instance.insert(vectors, payloads, ids)

    assert "Insert failed for document doc1" in str(exc_info.value)

    # Configure mock to return mixed success/failure for multiple documents
    mock_search_client.upload_documents.return_value = [
        {"status": True, "id": "doc1"},  # This should not cause failure
        {"status": False, "id": "doc2", "errorMessage": "Azure error"},
    ]

    vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    payloads = [{"user_id": "user1"}, {"user_id": "user2"}]
    ids = ["doc1", "doc2"]

    # Insert should raise an exception, but now check for doc2 failure
    with pytest.raises(Exception) as exc_info:
        instance.insert(vectors, payloads, ids)

    assert "Insert failed for document doc2" in str(exc_info.value) or "Insert failed for document doc1" in str(
        exc_info.value
    )


def test_insert_with_missing_payload_fields(azure_ai_search_instance):
    """Test inserting with payloads missing some of the expected fields."""
    instance, mock_search_client, _ = azure_ai_search_instance
    vectors = [[0.1, 0.2, 0.3]]
    payloads = [{"content": "Some content without user_id, run_id, or agent_id"}]
    ids = ["doc1"]

    # Mock successful response with a proper status_code
    mock_search_client.upload_documents.return_value = [
        {"id": "doc1", "status_code": 201}  # Simulating a successful response
    ]

    instance.insert(vectors, payloads, ids)

    # Verify upload_documents was called correctly
    mock_search_client.upload_documents.assert_called_once()
    args, _ = mock_search_client.upload_documents.call_args
    documents = args[0]
    # Verify document has payload but not the extra fields
    assert len(documents) == 1
    assert documents[0]["id"] == "doc1"
    assert documents[0]["vector"] == [0.1, 0.2, 0.3]
    assert documents[0]["payload"] == json.dumps(payloads[0])
    assert "user_id" not in documents[0]
    assert "run_id" not in documents[0]
    assert "agent_id" not in documents[0]


def test_insert_with_http_error(azure_ai_search_instance):
    """Test insert when Azure client throws an HTTP error."""
    instance, mock_search_client, _ = azure_ai_search_instance

    # Configure mock to raise an HttpResponseError
    mock_search_client.upload_documents.side_effect = HttpResponseError("Azure service error")

    vectors = [[0.1, 0.2, 0.3]]
    payloads = [{"user_id": "user1"}]
    ids = ["doc1"]

    # Insert should propagate the HTTP error
    with pytest.raises(HttpResponseError) as exc_info:
        instance.insert(vectors, payloads, ids)

    assert "Azure service error" in str(exc_info.value)


# --- Tests for search method ---


def test_search_basic(azure_ai_search_instance):
    """Test basic vector search without filters."""
    instance, mock_search_client, _ = azure_ai_search_instance

    # Ensure instance has a default vector_filter_mode
    instance.vector_filter_mode = "preFilter"

    # Configure mock to return search results
    mock_search_client.search.return_value = [
        {
            "id": "doc1",
            "@search.score": 0.95,
            "payload": json.dumps({"content": "Test content"}),
        }
    ]

    # Search with a vector
    query_text = "test query"  # Add a query string
    query_vector = [0.1, 0.2, 0.3]
    results = instance.search(query_text, query_vector, limit=5)  # Pass the query string

    # Verify search was called correctly
    mock_search_client.search.assert_called_once()
    _, kwargs = mock_search_client.search.call_args

    # Check parameters
    assert len(kwargs["vector_queries"]) == 1
    assert kwargs["vector_queries"][0].vector == query_vector
    assert kwargs["vector_queries"][0].k_nearest_neighbors == 5
    assert kwargs["vector_queries"][0].fields == "vector"
    assert kwargs["filter"] is None  # No filters
    assert kwargs["top"] == 5
    assert kwargs["vector_filter_mode"] == "preFilter"  # Now correctly set

    # Check results
    assert len(results) == 1
    assert results[0].id == "doc1"
    assert results[0].score == 0.95
    assert results[0].payload == {"content": "Test content"}


def test_init_with_valid_api_key(mock_clients):
    """Test __init__ with a valid API key and all required parameters."""
    mock_search_client, mock_index_client, mock_azure_key_credential = mock_clients

    instance = AzureAISearch(
        service_name="test-service",
        collection_name="test-index",
        api_key="test-api-key",
        embedding_model_dims=128,
        compression_type="scalar",
        use_float16=True,
        hybrid_search=True,
        vector_filter_mode="preFilter",
    )

    # Check attributes
    assert instance.service_name == "test-service"
    assert instance.api_key == "test-api-key"
    assert instance.index_name == "test-index"
    assert instance.collection_name == "test-index"
    assert instance.embedding_model_dims == 128
    assert instance.compression_type == "scalar"
    assert instance.use_float16 is True
    assert instance.hybrid_search is True
    assert instance.vector_filter_mode == "preFilter"

    # Check that AzureKeyCredential was used
    mock_azure_key_credential.assert_called_with("test-api-key")
    # Check that user agent was set
    mock_search_client._client._config.user_agent_policy.add_user_agent.assert_called_with("mem0")
    mock_index_client._client._config.user_agent_policy.add_user_agent.assert_called_with("mem0")
    # Check that create_col was called if collection does not exist
    mock_index_client.create_or_update_index.assert_called_once()


def test_init_with_default_api_key_triggers_default_credential(monkeypatch, mock_clients):
    """Test __init__ uses DefaultAzureCredential if api_key is None or placeholder."""
    mock_search_client, mock_index_client, mock_azure_key_credential = mock_clients

    # Patch DefaultAzureCredential to a mock so we can check if it's called
    with patch("mem0.vector_stores.azure_ai_search.DefaultAzureCredential") as mock_default_cred:
        # Test with api_key=None
        AzureAISearch(
            service_name="test-service",
            collection_name="test-index",
            api_key=None,
            embedding_model_dims=64,
        )
        mock_default_cred.assert_called_once()
        # Test with api_key=""
        AzureAISearch(
            service_name="test-service",
            collection_name="test-index",
            api_key="",
            embedding_model_dims=64,
        )
        assert mock_default_cred.call_count == 2
        # Test with api_key="your-api-key"
        AzureAISearch(
            service_name="test-service",
            collection_name="test-index",
            api_key="your-api-key",
            embedding_model_dims=64,
        )
        assert mock_default_cred.call_count == 3


def test_init_sets_compression_type_to_none_if_unspecified(mock_clients):
    """Test __init__ sets compression_type to 'none' if not specified."""
    mock_search_client, mock_index_client, _ = mock_clients

    instance = AzureAISearch(
        service_name="test-service",
        collection_name="test-index",
        api_key="test-api-key",
        embedding_model_dims=32,
    )
    assert instance.compression_type == "none"


def test_init_does_not_create_col_if_collection_exists(mock_clients):
    """Test __init__ does not call create_col if collection already exists."""
    mock_search_client, mock_index_client, _ = mock_clients
    # Simulate collection already exists
    mock_index_client.list_index_names.return_value = ["test-index"]

    AzureAISearch(
        service_name="test-service",
        collection_name="test-index",
        api_key="test-api-key",
        embedding_model_dims=16,
    )
    # create_or_update_index should not be called since collection exists
    mock_index_client.create_or_update_index.assert_not_called()


def test_init_calls_create_col_if_collection_missing(mock_clients):
    """Test __init__ calls create_col if collection does not exist."""
    mock_search_client, mock_index_client, _ = mock_clients
    # Simulate collection does not exist
    mock_index_client.list_index_names.return_value = []

    AzureAISearch(
        service_name="test-service",
        collection_name="missing-index",
        api_key="test-api-key",
        embedding_model_dims=16,
    )
    mock_index_client.create_or_update_index.assert_called_once()


# --- Tests for Field Mapping Fix ---

def test_generate_document_maps_all_mem0_fields(azure_ai_search_instance):
    """Test that _generate_document properly maps all mem0 payload fields to document fields."""
    instance, _, _ = azure_ai_search_instance
    
    # Sample payload that mem0 would create
    test_payload = {
        "user_id": "user123",
        "agent_id": "agent456", 
        "run_id": "run789",
        "data": "User likes playing chess",  # This should map to "memory" field
        "hash": "abcd1234efgh5678",
        "created_at": "2025-08-22T10:30:00-07:00",
        "updated_at": "2025-08-22T10:35:00-07:00",
        "memory_type": "episodic",
        "metadata": {"category": "hobbies", "confidence": 0.95}
    }
    
    test_vector = [0.1, 0.2, 0.3]
    test_id = "doc123"
    
    # Generate document using the private method
    document = instance._generate_document(test_vector, test_payload, test_id)
    
    # Verify core fields
    assert document["id"] == test_id
    assert document["vector"] == test_vector
    assert document["payload"] == json.dumps(test_payload)
    
    # Verify field mappings that fix the null field issue
    assert document["user_id"] == "user123"
    assert document["agent_id"] == "agent456"
    assert document["run_id"] == "run789"
    assert document["memory"] == "User likes playing chess"  # data -> memory mapping
    assert document["hash"] == "abcd1234efgh5678"
    assert document["created_at"] == "2025-08-22T10:30:00-07:00"
    assert document["updated_at"] == "2025-08-22T10:35:00-07:00"
    assert document["memory_type"] == "episodic"
    
    # Metadata should be JSON serialized
    expected_metadata = json.dumps({"category": "hobbies", "confidence": 0.95})
    assert document["metadata"] == expected_metadata


def test_generate_document_handles_missing_optional_fields(azure_ai_search_instance):
    """Test that _generate_document handles missing optional fields gracefully."""
    instance, _, _ = azure_ai_search_instance
    
    # Minimal payload with only required fields
    minimal_payload = {
        "user_id": "user123",
        "data": "User likes reading",
        "hash": "xyz789"
    }
    
    document = instance._generate_document([0.1, 0.2], minimal_payload, "doc456")
    
    # Should have required fields mapped
    assert document["user_id"] == "user123"
    assert document["memory"] == "User likes reading"  # data -> memory
    assert document["hash"] == "xyz789"
    
    # Missing fields should not be in document (Azure will set them to null)
    assert "agent_id" not in document
    assert "run_id" not in document
    assert "created_at" not in document
    assert "updated_at" not in document
    assert "memory_type" not in document
    assert "metadata" not in document


def test_generate_document_handles_metadata_types(azure_ai_search_instance):
    """Test that _generate_document properly handles different metadata types."""
    instance, _, _ = azure_ai_search_instance
    
    # Test with dict metadata (should be JSON serialized)
    payload_with_dict_metadata = {
        "user_id": "user123",
        "data": "Test content",
        "metadata": {"category": "test", "tags": ["tag1", "tag2"]}
    }
    
    document = instance._generate_document([0.1], payload_with_dict_metadata, "doc1")
    assert document["metadata"] == json.dumps({"category": "test", "tags": ["tag1", "tag2"]})
    
    # Test with string metadata (should remain as string)
    payload_with_string_metadata = {
        "user_id": "user123",
        "data": "Test content",
        "metadata": "simple string metadata"
    }
    
    document = instance._generate_document([0.1], payload_with_string_metadata, "doc2")
    assert document["metadata"] == "simple string metadata"
    
    # Test with None metadata (should be converted to string)
    payload_with_none_metadata = {
        "user_id": "user123",
        "data": "Test content", 
        "metadata": None
    }
    
    document = instance._generate_document([0.1], payload_with_none_metadata, "doc3")
    assert document["metadata"] is None


def test_insert_with_field_mapping_integration(azure_ai_search_instance):
    """Test that insert method uses the field mapping correctly."""
    instance, mock_search_client, _ = azure_ai_search_instance
    
    # Mock successful response
    mock_search_client.upload_documents.return_value = [
        {"status": True, "id": "doc1", "status_code": 201}
    ]
    
    # Use realistic mem0 payload
    vectors = [[0.1, 0.2, 0.3]]
    payloads = [{
        "user_id": "user123",
        "agent_id": "agent456",
        "data": "User enjoys hiking on weekends", 
        "hash": "hash123",
        "created_at": "2025-08-22T12:00:00-07:00",
        "memory_type": "episodic"
    }]
    ids = ["doc1"]
    
    instance.insert(vectors, payloads, ids)
    
    # Verify the document was created with proper field mapping
    mock_search_client.upload_documents.assert_called_once()
    args, _ = mock_search_client.upload_documents.call_args
    documents = args[0]
    
    doc = documents[0]
    assert doc["id"] == "doc1"
    assert doc["vector"] == [0.1, 0.2, 0.3]
    assert doc["payload"] == json.dumps(payloads[0])
    
    # Verify field mappings
    assert doc["user_id"] == "user123"
    assert doc["agent_id"] == "agent456"
    assert doc["memory"] == "User enjoys hiking on weekends"  # data -> memory
    assert doc["hash"] == "hash123"
    assert doc["created_at"] == "2025-08-22T12:00:00-07:00"
    assert doc["memory_type"] == "episodic"


def test_update_with_field_mapping(azure_ai_search_instance):
    """Test that update method uses proper field mapping."""
    instance, mock_search_client, _ = azure_ai_search_instance
    
    # Mock successful response
    mock_search_client.merge_or_upload_documents.return_value = [
        {"status": True, "id": "doc123", "status_code": 200}
    ]
    
    update_payload = {
        "user_id": "user123",
        "data": "Updated: User loves hiking and camping",
        "hash": "new_hash_value",
        "updated_at": "2025-08-22T13:00:00-07:00",
        "metadata": {"category": "outdoor_activities", "updated": True}
    }
    
    instance.update("doc123", payload=update_payload)
    
    # Verify the call was made with properly mapped fields
    mock_search_client.merge_or_upload_documents.assert_called_once()
    args, kwargs = mock_search_client.merge_or_upload_documents.call_args
    documents = kwargs["documents"]
    doc = documents[0]
    
    assert doc["id"] == "doc123"
    assert doc["payload"] == json.dumps(update_payload)
    assert doc["user_id"] == "user123"
    assert doc["memory"] == "Updated: User loves hiking and camping"  # data -> memory
    assert doc["hash"] == "new_hash_value"
    assert doc["updated_at"] == "2025-08-22T13:00:00-07:00"
    
    # Verify metadata is JSON serialized
    expected_metadata = json.dumps({"category": "outdoor_activities", "updated": True})
    assert doc["metadata"] == expected_metadata


def test_create_col_includes_all_mem0_fields(azure_ai_search_instance):
    """Test that create_col creates schema with all mem0 fields."""
    instance, _, mock_index_client = azure_ai_search_instance
    
    # create_col is called during initialization, check the call
    mock_index_client.create_or_update_index.assert_called_once()
    
    # Verify the index configuration
    args, _ = mock_index_client.create_or_update_index.call_args
    index = args[0]
    
    # Check that all expected fields are present in schema
    field_names = [f.name for f in index.fields]
    expected_fields = [
        "id", "user_id", "run_id", "agent_id", "memory", 
        "hash", "metadata", "memory_type", "created_at", 
        "updated_at", "vector", "payload"
    ]
    
    for expected_field in expected_fields:
        assert expected_field in field_names, f"Field '{expected_field}' missing from schema"
    
    # Verify specific field properties
    memory_field = next(f for f in index.fields if f.name == "memory")
    assert memory_field.searchable is True  # memory should be searchable
    
    metadata_field = next(f for f in index.fields if f.name == "metadata") 
    assert metadata_field.filterable is True  # metadata should be filterable, not searchable
    
    hash_field = next(f for f in index.fields if f.name == "hash")
    assert hash_field.filterable is True  # hash should be filterable
