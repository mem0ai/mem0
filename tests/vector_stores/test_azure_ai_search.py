import json
from unittest.mock import Mock, patch
import pytest
from azure.core.exceptions import ResourceNotFoundError, HttpResponseError

# Import the AzureAISearch class and OutputData model from your module.
from mem0.vector_stores.azure_ai_search import AzureAISearch


# Fixture to patch SearchClient and SearchIndexClient and create an instance of AzureAISearch.
@pytest.fixture
def mock_clients():
    with patch("mem0.vector_stores.azure_ai_search.SearchClient") as MockSearchClient, \
         patch("mem0.vector_stores.azure_ai_search.SearchIndexClient") as MockIndexClient:
        # Create mocked instances for search and index clients.
        mock_search_client = MockSearchClient.return_value
        mock_index_client = MockIndexClient.return_value

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
        mock_index_client.list_indexes = Mock(return_value=[])
        mock_index_client.list_index_names = Mock(return_value=["test-index"])
        mock_index_client.delete_index = Mock()
        # For col_info() we assume get_index returns an object with name and fields attributes.
        fake_index = Mock()
        fake_index.name = "test-index"
        fake_index.fields = ["id", "vector", "payload", "user_id", "run_id", "agent_id"]
        mock_index_client.get_index = Mock(return_value=fake_index)
        mock_index_client.close = Mock()

        yield mock_search_client, mock_index_client

@pytest.fixture
def azure_ai_search_instance(mock_clients):
    mock_search_client, mock_index_client = mock_clients
    # Create an instance with dummy parameters.
    instance = AzureAISearch(
        service_name="test-service",
        collection_name="test-index",
        api_key="test-api-key",
        embedding_model_dims=3,
        compression_type="binary",  # testing binary quantization option
        use_float16=True
    )
    # Return instance and clients for verification.
    return instance, mock_search_client, mock_index_client

# --- Original tests ---

def test_create_col(azure_ai_search_instance):
    instance, mock_search_client, mock_index_client = azure_ai_search_instance
    # Upon initialization, create_col should be called.
    mock_index_client.create_or_update_index.assert_called_once()
    # Optionally, you could inspect the call arguments for vector type.

def test_insert(azure_ai_search_instance):
    instance, mock_search_client, _ = azure_ai_search_instance
    vectors = [[0.1, 0.2, 0.3]]
    payloads = [{"user_id": "user1", "run_id": "run1"}]
    ids = ["doc1"]

    instance.insert(vectors, payloads, ids)

    mock_search_client.upload_documents.assert_called_once()
    args, _ = mock_search_client.upload_documents.call_args
    documents = args[0]
    # Update expected_doc to include extra fields from payload.
    expected_doc = {
        "id": "doc1",
        "vector": [0.1, 0.2, 0.3],
        "payload": json.dumps({"user_id": "user1", "run_id": "run1"}),
        "user_id": "user1",
        "run_id": "run1"
    }
    assert documents[0] == expected_doc

def test_search_preFilter(azure_ai_search_instance):
    instance, mock_search_client, _ = azure_ai_search_instance
    # Setup a fake search result returned by the mocked search method.
    fake_result = {
        "id": "doc1",
        "@search.score": 0.95,
        "payload": json.dumps({"user_id": "user1"})
    }
    # Configure the mock to return an iterator (list) with fake_result.
    mock_search_client.search.return_value = [fake_result]

    query_vector = [0.1, 0.2, 0.3]
    results = instance.search(query_vector, limit=1, filters={"user_id": "user1"}, vector_filter_mode="preFilter")

    # Verify that the search method was called with vector_filter_mode="preFilter".
    mock_search_client.search.assert_called_once()
    _, called_kwargs = mock_search_client.search.call_args
    assert called_kwargs.get("vector_filter_mode") == "preFilter"

    # Verify that the output is parsed correctly.
    assert len(results) == 1
    assert results[0].id == "doc1"
    assert results[0].score == 0.95
    assert results[0].payload == {"user_id": "user1"}

def test_search_postFilter(azure_ai_search_instance):
    instance, mock_search_client, _ = azure_ai_search_instance
    # Setup a fake search result for postFilter.
    fake_result = {
        "id": "doc2",
        "@search.score": 0.85,
        "payload": json.dumps({"user_id": "user2"})
    }
    mock_search_client.search.return_value = [fake_result]

    query_vector = [0.4, 0.5, 0.6]
    results = instance.search(query_vector, limit=1, filters={"user_id": "user2"}, vector_filter_mode="postFilter")

    mock_search_client.search.assert_called_once()
    _, called_kwargs = mock_search_client.search.call_args
    assert called_kwargs.get("vector_filter_mode") == "postFilter"

    assert len(results) == 1
    assert results[0].id == "doc2"
    assert results[0].score == 0.85
    assert results[0].payload == {"user_id": "user2"}

def test_delete(azure_ai_search_instance):
    instance, mock_search_client, _ = azure_ai_search_instance
    vector_id = "doc1"
    # Set delete_documents to return an iterable with a successful response.
    mock_search_client.delete_documents.return_value = [{"status": True, "id": vector_id}]
    instance.delete(vector_id)
    mock_search_client.delete_documents.assert_called_once_with(documents=[{"id": vector_id}])

def test_update(azure_ai_search_instance):
    instance, mock_search_client, _ = azure_ai_search_instance
    vector_id = "doc1"
    new_vector = [0.7, 0.8, 0.9]
    new_payload = {"user_id": "updated"}
    # Set merge_or_upload_documents to return an iterable with a successful response.
    mock_search_client.merge_or_upload_documents.return_value = [{"status": True, "id": vector_id}]
    instance.update(vector_id, vector=new_vector, payload=new_payload)
    mock_search_client.merge_or_upload_documents.assert_called_once()
    kwargs = mock_search_client.merge_or_upload_documents.call_args.kwargs
    document = kwargs["documents"][0]
    assert document["id"] == vector_id
    assert document["vector"] == new_vector
    assert document["payload"] == json.dumps(new_payload)
    # The update method will also add the 'user_id' field.
    assert document["user_id"] == "updated"

def test_get(azure_ai_search_instance):
    instance, mock_search_client, _ = azure_ai_search_instance
    fake_result = {
        "id": "doc1",
        "payload": json.dumps({"user_id": "user1"})
    }
    mock_search_client.get_document.return_value = fake_result
    result = instance.get("doc1")
    mock_search_client.get_document.assert_called_once_with(key="doc1")
    assert result.id == "doc1"
    assert result.payload == {"user_id": "user1"}
    assert result.score is None

def test_list(azure_ai_search_instance):
    instance, mock_search_client, _ = azure_ai_search_instance
    fake_result = {
        "id": "doc1",
        "@search.score": 0.99,
        "payload": json.dumps({"user_id": "user1"})
    }
    mock_search_client.search.return_value = [fake_result]
    # Call list with a simple filter.
    results = instance.list(filters={"user_id": "user1"}, limit=1)
    # Verify the search method was called with the proper parameters.
    expected_filter = instance._build_filter_expression({"user_id": "user1"})
    mock_search_client.search.assert_called_once_with(
        search_text="*",
        filter=expected_filter,
        top=1
    )
    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0].id == "doc1"

# --- New tests for practical end-user scenarios ---

def test_bulk_insert(azure_ai_search_instance):
    """Test inserting a batch of documents (common for initial data loading)."""
    instance, mock_search_client, _ = azure_ai_search_instance
    
    # Create a batch of 10 documents
    num_docs = 10
    vectors = [[0.1, 0.2, 0.3] for _ in range(num_docs)]
    payloads = [{"user_id": f"user{i}", "content": f"Test content {i}"} for i in range(num_docs)]
    ids = [f"doc{i}" for i in range(num_docs)]
    
    # Configure mock to return success for all documents
    mock_search_client.upload_documents.return_value = [
        {"status": True, "id": id_val} for id_val in ids
    ]
    
    # Insert the batch
    instance.insert(vectors, payloads, ids)
    
    # Verify the call
    mock_search_client.upload_documents.assert_called_once()
    args, _ = mock_search_client.upload_documents.call_args
    documents = args[0]
    assert len(documents) == num_docs
    
    # Verify the first and last document
    assert documents[0]["id"] == "doc0"
    assert documents[-1]["id"] == f"doc{num_docs-1}"


def test_insert_error_handling(azure_ai_search_instance):
    """Test how the class handles Azure errors during insertion."""
    instance, mock_search_client, _ = azure_ai_search_instance
    
    # Configure mock to return a failure for one document
    mock_search_client.upload_documents.return_value = [
        {"status": False, "id": "doc1", "errorMessage": "Azure error"}
    ]
    
    vectors = [[0.1, 0.2, 0.3]]
    payloads = [{"user_id": "user1"}]
    ids = ["doc1"]
    
    # Exception should be raised
    with pytest.raises(Exception) as exc_info:
        instance.insert(vectors, payloads, ids)
    
    assert "Insert failed" in str(exc_info.value)


def test_search_with_complex_filters(azure_ai_search_instance):
    """Test searching with multiple filter conditions as a user might need."""
    instance, mock_search_client, _ = azure_ai_search_instance
    
    # Configure mock response
    mock_search_client.search.return_value = [
        {
            "id": "doc1",
            "@search.score": 0.95,
            "payload": json.dumps({"user_id": "user1", "run_id": "run123", "agent_id": "agent456"})
        }
    ]
    
    # Search with multiple filters (common in multi-tenant or segmented applications)
    filters = {
        "user_id": "user1", 
        "run_id": "run123",
        "agent_id": "agent456"
    }
    results = instance.search([0.1, 0.2, 0.3], filters=filters)
    
    # Verify search was called with the correct filter expression
    mock_search_client.search.assert_called_once()
    _, kwargs = mock_search_client.search.call_args
    assert "filter" in kwargs
    
    # The filter should contain all three conditions
    filter_expr = kwargs["filter"]
    assert "user_id eq 'user1'" in filter_expr
    assert "run_id eq 'run123'" in filter_expr
    assert "agent_id eq 'agent456'" in filter_expr
    assert " and " in filter_expr  # Conditions should be joined by AND


def test_empty_search_results(azure_ai_search_instance):
    """Test behavior when search returns no results (common edge case)."""
    instance, mock_search_client, _ = azure_ai_search_instance
    
    # Configure mock to return empty results
    mock_search_client.search.return_value = []
    
    # Search with a non-matching query
    results = instance.search([0.9, 0.9, 0.9], limit=5)
    
    # Verify result handling
    assert len(results) == 0


def test_get_nonexistent_document(azure_ai_search_instance):
    """Test behavior when getting a document that doesn't exist (should handle gracefully)."""
    instance, mock_search_client, _ = azure_ai_search_instance
    
    # Configure mock to raise ResourceNotFoundError
    mock_search_client.get_document.side_effect = ResourceNotFoundError("Document not found")
    
    # Get a non-existent document
    result = instance.get("nonexistent_id")
    
    # Should return None instead of raising exception
    assert result is None


def test_azure_service_error(azure_ai_search_instance):
    """Test handling of Azure service errors (important for robustness)."""
    instance, mock_search_client, _ = azure_ai_search_instance
    
    # Configure mock to raise HttpResponseError
    http_error = HttpResponseError("Azure service is unavailable")
    mock_search_client.search.side_effect = http_error
    
    # Attempt to search
    with pytest.raises(HttpResponseError):
        instance.search([0.1, 0.2, 0.3])
    
    # Verify search was attempted
    mock_search_client.search.assert_called_once()


def test_realistic_workflow(azure_ai_search_instance):
    """Test a realistic workflow: insert → search → update → search again."""
    instance, mock_search_client, _ = azure_ai_search_instance
    
    # 1. Insert a document
    vector = [0.1, 0.2, 0.3]
    payload = {"user_id": "user1", "content": "Initial content"}
    doc_id = "workflow_doc"
    
    mock_search_client.upload_documents.return_value = [{"status": True, "id": doc_id}]
    instance.insert([vector], [payload], [doc_id])
    
    # 2. Search for the document
    mock_search_client.search.return_value = [
        {
            "id": doc_id,
            "@search.score": 0.95,
            "payload": json.dumps(payload)
        }
    ]
    results = instance.search(vector, filters={"user_id": "user1"})
    assert len(results) == 1
    assert results[0].id == doc_id
    
    # 3. Update the document
    updated_payload = {"user_id": "user1", "content": "Updated content"}
    mock_search_client.merge_or_upload_documents.return_value = [{"status": True, "id": doc_id}]
    instance.update(doc_id, payload=updated_payload)
    
    # 4. Search again to get updated document
    mock_search_client.search.return_value = [
        {
            "id": doc_id,
            "@search.score": 0.95,
            "payload": json.dumps(updated_payload)
        }
    ]
    results = instance.search(vector, filters={"user_id": "user1"})
    assert len(results) == 1
    assert results[0].id == doc_id
    assert results[0].payload["content"] == "Updated content"


def test_sanitize_special_characters(azure_ai_search_instance):
    """Test that special characters in filter values are properly sanitized."""
    instance, mock_search_client, _ = azure_ai_search_instance
    
    # Configure mock response
    mock_search_client.search.return_value = [
        {
            "id": "doc1",
            "@search.score": 0.95,
            "payload": json.dumps({"user_id": "user's-data"})
        }
    ]
    
    # Search with a filter that has special characters (common in real-world data)
    filters = {"user_id": "user's-data"}
    results = instance.search([0.1, 0.2, 0.3], filters=filters)
    
    # Verify search was called with properly escaped filter
    mock_search_client.search.assert_called_once()
    _, kwargs = mock_search_client.search.call_args
    assert "filter" in kwargs
    
    # The filter should have properly escaped single quotes
    filter_expr = kwargs["filter"]
    assert "user_id eq 'user''s-data'" in filter_expr


def test_list_collections(azure_ai_search_instance):
    """Test listing all collections/indexes (for management interfaces)."""
    instance, _, mock_index_client = azure_ai_search_instance
    
    # List the collections
    collections = instance.list_cols()
    
    # Verify the correct method was called
    mock_index_client.list_index_names.assert_called_once()
    
    # Check the result
    assert collections == ["test-index"]


def test_filter_with_numeric_values(azure_ai_search_instance):
    """Test filtering with numeric values (common for faceted search)."""
    instance, mock_search_client, _ = azure_ai_search_instance
    
    # Configure mock response
    mock_search_client.search.return_value = [
        {
            "id": "doc1",
            "@search.score": 0.95,
            "payload": json.dumps({"user_id": "user1", "count": 42})
        }
    ]
    
    # Search with a numeric filter
    # Note: In the actual implementation, numeric fields might need to be in the payload
    filters = {"count": 42}
    results = instance.search([0.1, 0.2, 0.3], filters=filters)
    
    # Verify the filter expression
    mock_search_client.search.assert_called_once()
    _, kwargs = mock_search_client.search.call_args
    filter_expr = kwargs["filter"]
    assert "count eq 42" in filter_expr  # No quotes for numbers


def test_error_on_update_nonexistent(azure_ai_search_instance):
    """Test behavior when updating a document that doesn't exist."""
    instance, mock_search_client, _ = azure_ai_search_instance
    
    # Configure mock to return a failure for the update
    mock_search_client.merge_or_upload_documents.return_value = [
        {"status": False, "id": "nonexistent", "errorMessage": "Document not found"}
    ]
    
    # Attempt to update a non-existent document
    with pytest.raises(Exception) as exc_info:
        instance.update("nonexistent", payload={"new": "data"})
    
    assert "Update failed" in str(exc_info.value)


def test_different_compression_types():
    """Test creating instances with different compression types (important for performance tuning)."""
    with patch("mem0.vector_stores.azure_ai_search.SearchClient"), \
         patch("mem0.vector_stores.azure_ai_search.SearchIndexClient"):
        
        # Test with scalar compression
        scalar_instance = AzureAISearch(
            service_name="test-service",
            collection_name="scalar-index",
            api_key="test-api-key",
            embedding_model_dims=3,
            compression_type="scalar",
            use_float16=False
        )
        
        # Test with no compression
        no_compression_instance = AzureAISearch(
            service_name="test-service",
            collection_name="no-compression-index",
            api_key="test-api-key",
            embedding_model_dims=3,
            compression_type=None,
            use_float16=False
        )
        
        # No assertions needed - we're just verifying that initialization doesn't fail


def test_high_dimensional_vectors():
    """Test handling of high-dimensional vectors typical in AI embeddings."""
    with patch("mem0.vector_stores.azure_ai_search.SearchClient") as MockSearchClient, \
         patch("mem0.vector_stores.azure_ai_search.SearchIndexClient"):
        
        # Configure the mock client
        mock_search_client = MockSearchClient.return_value
        mock_search_client.upload_documents = Mock()
        mock_search_client.upload_documents.return_value = [{"status": True, "id": "doc1"}]
        
        # Create an instance with higher dimensions like those from embedding models
        high_dim_instance = AzureAISearch(
            service_name="test-service",
            collection_name="high-dim-index",
            api_key="test-api-key",
            embedding_model_dims=1536,  # Common for models like OpenAI's embeddings
            compression_type="binary",  # Compression often used with high-dim vectors
            use_float16=True  # Reduced precision often used for memory efficiency
        )
        
        # Create a high-dimensional vector (stub with zeros for testing)
        high_dim_vector = [0.0] * 1536
        payload = {"user_id": "user1"}
        doc_id = "high_dim_doc"
        
        # Insert the document
        high_dim_instance.insert([high_dim_vector], [payload], [doc_id])
        
        # Verify the insert was called with the full vector
        mock_search_client.upload_documents.assert_called_once()
        args, _ = mock_search_client.upload_documents.call_args
        documents = args[0]
        assert len(documents[0]["vector"]) == 1536