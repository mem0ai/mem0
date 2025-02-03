import json
from unittest.mock import Mock, patch

import pytest

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
        mock_search_client.search = Mock()
        mock_search_client.delete_documents = Mock()
        mock_search_client.merge_or_upload_documents = Mock()
        mock_search_client.get_document = Mock()
        mock_search_client.close = Mock()

        # Stub required methods on index_client.
        mock_index_client.create_or_update_index = Mock()
        mock_index_client.list_indexes = Mock(return_value=[])
        mock_index_client.delete_index = Mock()
        # For col_info() we assume get_index returns an object with name and fields attributes.
        fake_index = Mock()
        fake_index.name = "test-index"
        fake_index.fields = ["id", "vector", "payload"]
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
    # Configure the mock to return an iterator (e.g., a list) with fake_result.
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
    instance.delete(vector_id)
    mock_search_client.delete_documents.assert_called_once_with(documents=[{"id": vector_id}])

def test_update(azure_ai_search_instance):
    instance, mock_search_client, _ = azure_ai_search_instance
    vector_id = "doc1"
    new_vector = [0.7, 0.8, 0.9]
    new_payload = {"user_id": "updated"}
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
