import pytest
from unittest.mock import MagicMock

from mem0.vector_stores.bedrock_kb import BedrockKB

KB_ID = "test-kb-id"
DATA_SOURCE_ID = "test-ds-id"
DATA_SOURCE_BUCKET = "test-bucket"
REGION = "us-west-2"


@pytest.fixture
def mock_boto_clients():
    """Fixture providing mock boto3 clients to inject into BedrockKB instances."""
    runtime_client = MagicMock()
    agent_client = MagicMock()
    s3_client = MagicMock()

    yield {
        "runtime": runtime_client,
        "agent": agent_client,
        "s3": s3_client,
    }


@pytest.fixture
def store(mock_boto_clients):
    """Create a BedrockKB instance with mock clients injected directly."""
    kb = BedrockKB(
        knowledge_base_id=KB_ID,
        data_source_id=DATA_SOURCE_ID,
        data_source_bucket=DATA_SOURCE_BUCKET,
        region_name=REGION,
        number_of_results=10,
        knowledge_base_type="MANAGED",
        use_agentic_retrieval=False,
    )
    kb._runtime_client = mock_boto_clients["runtime"]
    kb._agent_client = mock_boto_clients["agent"]
    kb._s3_client = mock_boto_clients["s3"]
    return kb


class TestInit:
    def test_init_with_params(self):
        """Test initialization with explicit parameters."""
        kb = BedrockKB(
            knowledge_base_id=KB_ID,
            data_source_id=DATA_SOURCE_ID,
            data_source_bucket=DATA_SOURCE_BUCKET,
            region_name=REGION,
            number_of_results=10,
            knowledge_base_type="VECTOR",
        )

        assert kb.knowledge_base_id == KB_ID
        assert kb.data_source_id == DATA_SOURCE_ID
        assert kb.data_source_bucket == DATA_SOURCE_BUCKET
        assert kb.region_name == REGION
        assert kb.number_of_results == 10
        assert kb.knowledge_base_type == "VECTOR"

    def test_init_with_env_vars(self, monkeypatch):
        """Test initialization falls back to environment variables."""
        monkeypatch.setenv("KNOWLEDGE_BASE_ID", "env-kb-id")
        monkeypatch.setenv("BEDROCK_DATA_SOURCE_ID", "env-ds-id")
        monkeypatch.setenv("BEDROCK_DATA_SOURCE_BUCKET", "env-bucket")
        monkeypatch.setenv("AWS_REGION", "eu-west-1")

        kb = BedrockKB()

        assert kb.knowledge_base_id == "env-kb-id"
        assert kb.data_source_id == "env-ds-id"
        assert kb.data_source_bucket == "env-bucket"
        assert kb.region_name == "eu-west-1"

    def test_init_defaults(self, monkeypatch):
        """Test initialization defaults when no params or env vars are set."""
        monkeypatch.delenv("KNOWLEDGE_BASE_ID", raising=False)
        monkeypatch.delenv("BEDROCK_DATA_SOURCE_ID", raising=False)
        monkeypatch.delenv("BEDROCK_DATA_SOURCE_BUCKET", raising=False)
        monkeypatch.delenv("AWS_REGION", raising=False)

        kb = BedrockKB()

        assert kb.knowledge_base_id == ""
        assert kb.data_source_id == ""
        assert kb.data_source_bucket == ""
        assert kb.region_name == "us-east-1"
        assert kb.number_of_results == 5
        assert kb.knowledge_base_type == "MANAGED"


class TestSearch:
    def test_search_managed_config(self, store, mock_boto_clients):
        """Test search with MANAGED knowledge base type returns correct format."""
        mock_boto_clients["runtime"].retrieve.return_value = {
            "retrievalResults": [
                {
                    "content": {"text": "Hello world"},
                    "location": {"s3Location": {"uri": "s3://bucket/mem0/doc1.txt"}},
                    "score": 0.95,
                },
                {
                    "content": {"text": "Goodbye world"},
                    "location": {"s3Location": {"uri": "s3://bucket/mem0/doc2.txt"}},
                    "score": 0.80,
                },
            ]
        }

        results = store.search(query="hello", top_k=2)

        mock_boto_clients["runtime"].retrieve.assert_called_once_with(
            knowledgeBaseId=KB_ID,
            retrievalQuery={"text": "hello"},
            retrievalConfiguration={"managedSearchConfiguration": {"numberOfResults": 2}},
        )
        assert len(results) == 2
        assert results[0].id == "doc1"
        assert results[0].score == 0.95
        assert results[0].payload["data"] == "Hello world"
        assert "doc1" in results[0].payload["source"]

    def test_search_vector_config(self, mock_boto_clients):
        """Test search with VECTOR knowledge base type uses vectorSearchConfiguration."""
        vector_store = BedrockKB(
            knowledge_base_id=KB_ID,
            data_source_id=DATA_SOURCE_ID,
            data_source_bucket=DATA_SOURCE_BUCKET,
            region_name=REGION,
            knowledge_base_type="VECTOR",
            use_agentic_retrieval=False,
        )
        vector_store._runtime_client = mock_boto_clients["runtime"]
        vector_store._agent_client = mock_boto_clients["agent"]
        vector_store._s3_client = mock_boto_clients["s3"]
        mock_boto_clients["runtime"].retrieve.return_value = {
            "retrievalResults": [
                {
                    "content": {"text": "Vector result"},
                    "location": {"s3Location": {"uri": "s3://bucket/mem0/vec1.txt"}},
                    "score": 0.88,
                },
            ]
        }

        results = vector_store.search(query="test query", top_k=3)

        mock_boto_clients["runtime"].retrieve.assert_called_once_with(
            knowledgeBaseId=KB_ID,
            retrievalQuery={"text": "test query"},
            retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": 3}},
        )
        assert len(results) == 1
        assert results[0].score == 0.88

    def test_search_returns_empty_on_error(self, store, mock_boto_clients):
        """Test search returns empty list on exception."""
        mock_boto_clients["runtime"].retrieve.side_effect = Exception("Service unavailable")

        results = store.search(query="fail")

        assert results == []


class TestInsert:
    def test_insert_uploads_to_s3_and_triggers_ingestion(self, store, mock_boto_clients):
        """Test insert uploads documents to S3 and starts ingestion."""
        payloads = [
            {"data": "Document one", "metadata": {"user_id": "alice"}},
            {"data": "Document two", "metadata": {"user_id": "bob"}},
        ]
        ids = ["id-1", "id-2"]

        result = store.insert(vectors=[[0.1, 0.2], [0.3, 0.4]], payloads=payloads, ids=ids)

        assert result == ["id-1", "id-2"]
        assert mock_boto_clients["s3"].put_object.call_count == 4

        # Verify first document upload
        first_call = mock_boto_clients["s3"].put_object.call_args_list[0]
        assert first_call.kwargs["Bucket"] == DATA_SOURCE_BUCKET
        assert first_call.kwargs["Key"] == "mem0/alice/id-1.txt"
        assert first_call.kwargs["Body"] == "Document one"

        # Verify ingestion was triggered
        mock_boto_clients["agent"].start_ingestion_job.assert_called_once_with(
            knowledgeBaseId=KB_ID,
            dataSourceId=DATA_SOURCE_ID,
        )

    def test_insert_generates_ids_when_not_provided(self, store, mock_boto_clients):
        """Test insert generates UUIDs when no ids are provided."""
        payloads = [{"data": "Some content"}]

        result = store.insert(vectors=[[0.1]], payloads=payloads)

        assert len(result) == 1
        # Should be a valid UUID string
        assert len(result[0]) == 36
        assert mock_boto_clients["s3"].put_object.call_count == 2

    def test_insert_no_bucket_does_nothing(self, mock_boto_clients):
        """Test insert returns None when no bucket is configured."""
        kb = BedrockKB(
            knowledge_base_id=KB_ID,
            data_source_id=DATA_SOURCE_ID,
            data_source_bucket="",
            region_name=REGION,
        )

        result = kb.insert(vectors=[[0.1]], payloads=[{"data": "test"}], ids=["id-1"])

        assert result is None
        mock_boto_clients["s3"].put_object.assert_not_called()


class TestDelete:
    def test_delete_removes_from_s3_and_triggers_ingestion(self, store, mock_boto_clients):
        """Test delete removes the object from S3 and triggers re-sync."""
        store.delete("doc-123")

        mock_boto_clients["s3"].delete_object.assert_any_call(
            Bucket=DATA_SOURCE_BUCKET,
            Key="mem0/_default/doc-123.txt",
        )
        mock_boto_clients["agent"].start_ingestion_job.assert_called_once_with(
            knowledgeBaseId=KB_ID,
            dataSourceId=DATA_SOURCE_ID,
        )

    def test_delete_no_bucket_does_nothing(self, mock_boto_clients):
        """Test delete does nothing when no bucket is configured."""
        kb = BedrockKB(
            knowledge_base_id=KB_ID,
            data_source_id=DATA_SOURCE_ID,
            data_source_bucket="",
            region_name=REGION,
        )

        kb.delete("doc-123")

        mock_boto_clients["s3"].delete_object.assert_not_called()

    def test_delete_handles_s3_error(self, store, mock_boto_clients):
        """Test delete handles S3 errors gracefully."""
        mock_boto_clients["s3"].delete_object.side_effect = Exception("Access Denied")

        # Should not raise
        store.delete("doc-123")

        mock_boto_clients["agent"].start_ingestion_job.assert_not_called()


class TestUpdate:
    def test_update_reuploads_and_triggers_ingestion(self, store, mock_boto_clients):
        """Test update re-uploads the document and triggers ingestion."""
        store.update("doc-456", payload={"data": "Updated content"})

        mock_boto_clients["s3"].put_object.assert_any_call(
            Bucket=DATA_SOURCE_BUCKET,
            Key="mem0/_default/doc-456.txt",
            Body="Updated content",
        )
        mock_boto_clients["agent"].start_ingestion_job.assert_called_once_with(
            knowledgeBaseId=KB_ID,
            dataSourceId=DATA_SOURCE_ID,
        )

    def test_update_with_string_payload(self, store, mock_boto_clients):
        """Test update with a non-dict payload converts to string."""
        store.update("doc-789", payload="Plain text payload")

        mock_boto_clients["s3"].put_object.assert_any_call(
            Bucket=DATA_SOURCE_BUCKET,
            Key="mem0/_default/doc-789.txt",
            Body="Plain text payload",
        )

    def test_update_no_payload_does_nothing(self, store, mock_boto_clients):
        """Test update with no payload does not upload."""
        store.update("doc-123", payload=None)

        mock_boto_clients["s3"].put_object.assert_not_called()
        mock_boto_clients["agent"].start_ingestion_job.assert_not_called()


class TestGet:
    def test_get_fetches_from_s3(self, store, mock_boto_clients):
        """Test get retrieves document content from S3."""
        mock_body = MagicMock()
        mock_body.read.return_value = b"Retrieved content"
        mock_boto_clients["s3"].get_object.return_value = {"Body": mock_body}

        result = store.get("doc-abc")

        mock_boto_clients["s3"].get_object.assert_called_once_with(
            Bucket=DATA_SOURCE_BUCKET,
            Key="mem0/_default/doc-abc.txt",
        )
        assert result.id == "doc-abc"
        assert result.payload["data"] == "Retrieved content"

    def test_get_returns_none_on_error(self, store, mock_boto_clients):
        """Test get returns None when S3 raises an exception."""
        mock_boto_clients["s3"].get_object.side_effect = Exception("NoSuchKey")

        result = store.get("nonexistent")

        assert result is None

    def test_get_no_bucket_returns_none(self, mock_boto_clients):
        """Test get returns None when no bucket is configured."""
        kb = BedrockKB(
            knowledge_base_id=KB_ID,
            data_source_id=DATA_SOURCE_ID,
            data_source_bucket="",
            region_name=REGION,
        )

        result = kb.get("doc-123")

        assert result is None
        mock_boto_clients["s3"].get_object.assert_not_called()


class TestList:
    def test_list_returns_s3_objects(self, store, mock_boto_clients):
        """Test list returns documents from S3 prefix."""
        mock_boto_clients["s3"].list_objects_v2.return_value = {
            "Contents": [
                {"Key": "mem0/doc-1.txt"},
                {"Key": "mem0/doc-2.txt"},
                {"Key": "mem0/doc-3.txt"},
            ]
        }

        results = store.list()

        mock_boto_clients["s3"].list_objects_v2.assert_called_once_with(
            Bucket=DATA_SOURCE_BUCKET,
            Prefix="mem0/",
            MaxKeys=100,
        )
        assert len(results[0]) == 3
        assert results[0][0].id == "doc-1"
        assert results[0][1].id == "doc-2"
        assert results[0][2].id == "doc-3"

    def test_list_with_top_k(self, store, mock_boto_clients):
        """Test list respects top_k parameter."""
        mock_boto_clients["s3"].list_objects_v2.return_value = {"Contents": []}

        store.list(top_k=25)

        mock_boto_clients["s3"].list_objects_v2.assert_called_once_with(
            Bucket=DATA_SOURCE_BUCKET,
            Prefix="mem0/",
            MaxKeys=25,
        )

    def test_list_no_bucket_returns_empty(self, mock_boto_clients):
        """Test list returns empty list when no bucket is configured."""
        kb = BedrockKB(
            knowledge_base_id=KB_ID,
            data_source_id=DATA_SOURCE_ID,
            data_source_bucket="",
            region_name=REGION,
        )

        results = kb.list()

        assert results == [[]]
        mock_boto_clients["s3"].list_objects_v2.assert_not_called()

    def test_list_handles_error(self, store, mock_boto_clients):
        """Test list returns empty list on S3 error."""
        mock_boto_clients["s3"].list_objects_v2.side_effect = Exception("Access Denied")

        results = store.list()

        assert results == [[]]


class TestErrorHandlingMissingBucket:
    """Tests verifying behavior when data_source_bucket is not configured."""

    def test_insert_without_bucket(self, mock_boto_clients):
        kb = BedrockKB(knowledge_base_id=KB_ID, data_source_bucket="")
        result = kb.insert(vectors=[[0.1]], payloads=[{"data": "x"}], ids=["id1"])
        assert result is None

    def test_delete_without_bucket(self, mock_boto_clients):
        kb = BedrockKB(knowledge_base_id=KB_ID, data_source_bucket="")
        # Should not raise
        kb.delete("id1")
        mock_boto_clients["s3"].delete_object.assert_not_called()

    def test_get_without_bucket(self, mock_boto_clients):
        kb = BedrockKB(knowledge_base_id=KB_ID, data_source_bucket="")
        result = kb.get("id1")
        assert result is None

    def test_list_without_bucket(self, mock_boto_clients):
        kb = BedrockKB(knowledge_base_id=KB_ID, data_source_bucket="")
        result = kb.list()
        assert result == [[]]


class TestInsertDirect:
    """Tests for CUSTOM data source (IngestKnowledgeBaseDocuments) path."""

    def test_insert_direct_calls_ingest_api(self):
        from mem0.vector_stores.bedrock_kb import BedrockKB

        kb = BedrockKB(
            knowledge_base_id="TEST_KB",
            data_source_id="DS_CUSTOM",
            region_name="us-west-2",
            data_source_type="CUSTOM",
        )
        mock_client = MagicMock()
        kb._agent_client = mock_client

        result = kb.insert(
            vectors=None,
            payloads=[{"data": "Test document content", "metadata": {"user_id": "alice"}}],
            ids=["doc-001"],
        )

        assert result == ["doc-001"]
        mock_client.ingest_knowledge_base_documents.assert_called_once()
        call_kwargs = mock_client.ingest_knowledge_base_documents.call_args.kwargs
        assert call_kwargs["knowledgeBaseId"] == "TEST_KB"
        assert call_kwargs["dataSourceId"] == "DS_CUSTOM"
        assert len(call_kwargs["documents"]) == 1
        doc = call_kwargs["documents"][0]
        assert doc["content"]["dataSourceType"] == "CUSTOM"
        assert doc["content"]["custom"]["customDocumentIdentifier"]["id"] == "doc-001"
        assert doc["content"]["custom"]["inlineContent"]["type"] == "TEXT"
        assert doc["content"]["custom"]["inlineContent"]["textContent"]["data"] == "Test document content"

    def test_insert_direct_includes_metadata(self):
        from mem0.vector_stores.bedrock_kb import BedrockKB

        kb = BedrockKB(
            knowledge_base_id="TEST_KB",
            data_source_id="DS_CUSTOM",
            data_source_type="CUSTOM",
        )
        mock_client = MagicMock()
        kb._agent_client = mock_client

        kb.insert(
            vectors=None,
            payloads=[{"data": "content", "metadata": {"user_id": "bob", "category": "faq"}}],
        )

        call_kwargs = mock_client.ingest_knowledge_base_documents.call_args.kwargs
        doc = call_kwargs["documents"][0]
        assert doc["metadata"]["type"] == "IN_LINE_ATTRIBUTE"
        attrs = {a["key"]: a["value"]["stringValue"] for a in doc["metadata"]["inlineAttributes"]}
        assert attrs["user_id"] == "bob"
        assert attrs["category"] == "faq"

    def test_insert_direct_no_data_source_id_returns_none(self):
        from mem0.vector_stores.bedrock_kb import BedrockKB

        kb = BedrockKB(
            knowledge_base_id="TEST_KB",
            data_source_type="CUSTOM",
        )
        kb._data_source_id = ""

        result = kb.insert(vectors=None, payloads=[{"data": "test"}])
        assert result is None

    def test_insert_direct_batches_over_10(self):
        from mem0.vector_stores.bedrock_kb import BedrockKB

        kb = BedrockKB(
            knowledge_base_id="TEST_KB",
            data_source_id="DS_CUSTOM",
            data_source_type="CUSTOM",
        )
        mock_client = MagicMock()
        kb._agent_client = mock_client

        # Insert 12 documents - should make 2 API calls (10 + 2)
        payloads = [{"data": f"doc {i}"} for i in range(12)]
        result = kb.insert(vectors=None, payloads=payloads)

        assert len(result) == 12
        assert mock_client.ingest_knowledge_base_documents.call_count == 2

    def test_insert_direct_s3_reference(self):
        from mem0.vector_stores.bedrock_kb import BedrockKB

        kb = BedrockKB(
            knowledge_base_id="TEST_KB",
            data_source_id="DS_CUSTOM",
            data_source_type="CUSTOM",
        )
        mock_client = MagicMock()
        kb._agent_client = mock_client

        result = kb.insert(
            vectors=None,
            payloads=[{"s3_uri": "s3://my-bucket/docs/file.pdf", "metadata": {"source": "s3"}}],
            ids=["s3-doc-001"],
        )

        assert result == ["s3-doc-001"]
        call_kwargs = mock_client.ingest_knowledge_base_documents.call_args.kwargs
        doc = call_kwargs["documents"][0]
        assert doc["content"]["custom"]["sourceType"] == "S3_LOCATION"
        assert doc["content"]["custom"]["s3Location"]["uri"] == "s3://my-bucket/docs/file.pdf"

    def test_insert_direct_binary_content(self):
        from mem0.vector_stores.bedrock_kb import BedrockKB

        kb = BedrockKB(
            knowledge_base_id="TEST_KB",
            data_source_id="DS_CUSTOM",
            data_source_type="CUSTOM",
        )
        mock_client = MagicMock()
        kb._agent_client = mock_client

        result = kb.insert(
            vectors=None,
            payloads=[{"data": "base64encodedcontent", "mime_type": "application/pdf"}],
            ids=["pdf-001"],
        )

        assert result == ["pdf-001"]
        call_kwargs = mock_client.ingest_knowledge_base_documents.call_args.kwargs
        doc = call_kwargs["documents"][0]
        assert doc["content"]["custom"]["inlineContent"]["type"] == "BYTE"
        assert doc["content"]["custom"]["inlineContent"]["byteContent"]["mimeType"] == "application/pdf"
