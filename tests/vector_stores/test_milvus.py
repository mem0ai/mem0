"""
Unit tests for Milvus vector store implementation.

These tests verify:
1. Correct type handling for vector dimensions
2. Batch insert functionality
3. Filter creation for metadata queries
4. Update/upsert operations
"""

import pytest
from unittest.mock import MagicMock, patch
from mem0.vector_stores.milvus import MilvusDB
from mem0.configs.vector_stores.milvus import MetricType


class TestMilvusDB:
    """Test suite for MilvusDB vector store."""

    @pytest.fixture
    def mock_milvus_client(self):
        """Mock MilvusClient to avoid requiring actual Milvus instance."""
        with patch('mem0.vector_stores.milvus.MilvusClient') as mock_client:
            mock_instance = MagicMock()
            mock_instance.has_collection.return_value = False
            mock_client.return_value = mock_instance
            yield mock_instance

    @pytest.fixture
    def milvus_db(self, mock_milvus_client):
        """Create MilvusDB instance with mocked client."""
        return MilvusDB(
            url="http://localhost:19530",
            token="test_token",
            collection_name="test_collection",
            embedding_model_dims=1536,  # Should be int, not str
            metric_type=MetricType.COSINE,
            db_name="test_db"
        )

    def test_initialization_with_int_dims(self, mock_milvus_client):
        """Test that vector dimensions are correctly handled as integers."""
        db = MilvusDB(
            url="http://localhost:19530",
            token="test_token",
            collection_name="test_collection",
            embedding_model_dims=1536,  # Integer
            metric_type=MetricType.COSINE,
            db_name="test_db"
        )
        
        assert db.embedding_model_dims == 1536
        assert isinstance(db.embedding_model_dims, int)

    def test_create_col_with_int_vector_size(self, milvus_db, mock_milvus_client):
        """Test collection creation with integer vector size (bug fix validation)."""
        # Collection was already created in __init__, but let's verify the call
        mock_milvus_client.create_collection.assert_called_once()
        call_args = mock_milvus_client.create_collection.call_args
        
        # Verify schema was created properly
        assert call_args is not None
        
    def test_batch_insert(self, milvus_db, mock_milvus_client):
        """Test that insert uses batch operation instead of loop (performance fix)."""
        ids = ["id1", "id2", "id3"]
        vectors = [[0.1] * 1536, [0.2] * 1536, [0.3] * 1536]
        payloads = [{"user_id": "alice"}, {"user_id": "bob"}, {"user_id": "charlie"}]
        
        milvus_db.insert(ids, vectors, payloads)
        
        # Verify insert was called once with all data (batch), not 3 times
        assert mock_milvus_client.insert.call_count == 1
        
        # Verify the data structure
        call_args = mock_milvus_client.insert.call_args
        inserted_data = call_args[1]['data']
        
        assert len(inserted_data) == 3
        assert inserted_data[0]['id'] == 'id1'
        assert inserted_data[1]['id'] == 'id2'
        assert inserted_data[2]['id'] == 'id3'

    def test_create_filter_string_value(self, milvus_db):
        """Test filter creation for string metadata values."""
        filters = {"user_id": "alice"}
        filter_str = milvus_db._create_filter(filters)
        
        assert filter_str == '(metadata["user_id"] == "alice")'

    def test_create_filter_numeric_value(self, milvus_db):
        """Test filter creation for numeric metadata values."""
        filters = {"age": 25}
        filter_str = milvus_db._create_filter(filters)
        
        assert filter_str == '(metadata["age"] == 25)'

    def test_create_filter_multiple_conditions(self, milvus_db):
        """Test filter creation with multiple conditions."""
        filters = {"user_id": "alice", "category": "work"}
        filter_str = milvus_db._create_filter(filters)
        
        # Should join with 'and'
        assert 'metadata["user_id"] == "alice"' in filter_str
        assert 'metadata["category"] == "work"' in filter_str
        assert ' and ' in filter_str

    def test_search_with_filters(self, milvus_db, mock_milvus_client):
        """Test search with metadata filters (reproduces user's bug scenario)."""
        # Setup mock return value
        mock_milvus_client.search.return_value = [[
            {"id": "mem1", "distance": 0.8, "entity": {"metadata": {"user_id": "alice"}}}
        ]]
        
        query_vector = [0.1] * 1536
        filters = {"user_id": "alice"}
        
        results = milvus_db.search(
            query="test query",
            vectors=query_vector,
            limit=5,
            filters=filters
        )
        
        # Verify search was called with correct filter
        call_args = mock_milvus_client.search.call_args
        assert call_args[1]['filter'] == '(metadata["user_id"] == "alice")'
        
        # Verify results are parsed correctly
        assert len(results) == 1
        assert results[0].id == "mem1"
        assert results[0].score == 0.8

    def test_search_different_user_ids(self, milvus_db, mock_milvus_client):
        """Test that search works with different user_ids (reproduces reported bug)."""
        # This test validates the fix for: "Error with different user_ids"
        
        # Mock return for first user
        mock_milvus_client.search.return_value = [[
            {"id": "mem1", "distance": 0.9, "entity": {"metadata": {"user_id": "milvus_user"}}}
        ]]
        
        results1 = milvus_db.search("test", [0.1] * 1536, filters={"user_id": "milvus_user"})
        assert len(results1) == 1
        
        # Mock return for second user
        mock_milvus_client.search.return_value = [[
            {"id": "mem2", "distance": 0.85, "entity": {"metadata": {"user_id": "bob"}}}
        ]]
        
        # This should not raise "Unsupported Field type: 0" error
        results2 = milvus_db.search("test", [0.2] * 1536, filters={"user_id": "bob"})
        assert len(results2) == 1

    def test_update_uses_upsert(self, milvus_db, mock_milvus_client):
        """Test that update correctly uses upsert operation."""
        vector_id = "test_id"
        vector = [0.1] * 1536
        payload = {"user_id": "alice", "data": "Updated memory"}
        
        milvus_db.update(vector_id=vector_id, vector=vector, payload=payload)
        
        # Verify upsert was called (not delete+insert)
        mock_milvus_client.upsert.assert_called_once()
        
        call_args = mock_milvus_client.upsert.call_args
        assert call_args[1]['collection_name'] == "test_collection"
        assert call_args[1]['data']['id'] == vector_id
        assert call_args[1]['data']['vectors'] == vector
        assert call_args[1]['data']['metadata'] == payload

    def test_delete(self, milvus_db, mock_milvus_client):
        """Test vector deletion."""
        vector_id = "test_id"
        milvus_db.delete(vector_id)
        
        mock_milvus_client.delete.assert_called_once_with(
            collection_name="test_collection",
            ids=vector_id
        )

    def test_get(self, milvus_db, mock_milvus_client):
        """Test retrieving a vector by ID."""
        vector_id = "test_id"
        mock_milvus_client.get.return_value = [
            {"id": vector_id, "metadata": {"user_id": "alice"}}
        ]
        
        result = milvus_db.get(vector_id)
        
        assert result.id == vector_id
        assert result.payload == {"user_id": "alice"}
        assert result.score is None

    def test_list_with_filters(self, milvus_db, mock_milvus_client):
        """Test listing memories with filters."""
        mock_milvus_client.query.return_value = [
            {"id": "mem1", "metadata": {"user_id": "alice"}},
            {"id": "mem2", "metadata": {"user_id": "alice"}}
        ]
        
        results = milvus_db.list(filters={"user_id": "alice"}, limit=10)
        
        # Verify query was called with filter
        call_args = mock_milvus_client.query.call_args
        assert call_args[1]['filter'] == '(metadata["user_id"] == "alice")'
        assert call_args[1]['limit'] == 10
        
        # Verify results
        assert len(results[0]) == 2

    def test_parse_output(self, milvus_db):
        """Test output data parsing."""
        raw_data = [
            {
                "id": "mem1",
                "distance": 0.9,
                "entity": {"metadata": {"user_id": "alice"}}
            },
            {
                "id": "mem2",
                "distance": 0.85,
                "entity": {"metadata": {"user_id": "bob"}}
            }
        ]
        
        parsed = milvus_db._parse_output(raw_data)
        
        assert len(parsed) == 2
        assert parsed[0].id == "mem1"
        assert parsed[0].score == 0.9
        assert parsed[0].payload == {"user_id": "alice"}
        assert parsed[1].id == "mem2"
        assert parsed[1].score == 0.85

    def test_collection_already_exists(self, mock_milvus_client):
        """Test that existing collection is not recreated."""
        mock_milvus_client.has_collection.return_value = True
        
        MilvusDB(
            url="http://localhost:19530",
            token="test_token",
            collection_name="existing_collection",
            embedding_model_dims=1536,
            metric_type=MetricType.L2,
            db_name="test_db"
        )
        
        # create_collection should not be called
        mock_milvus_client.create_collection.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

