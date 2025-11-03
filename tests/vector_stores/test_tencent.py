"""
Unit tests for TencentVectorDB implementation.

These tests verify:
1. Correct type handling for vector dimensions
2. Batch insert functionality
3. Filter creation for metadata queries
4. Update/upsert operations
"""

from unittest.mock import MagicMock, patch

import pytest

from mem0.vector_stores.tencent import TencentVectorDB


class TestTencentVectorDB:
    """Test suite for TencentVectorDB vector store."""

    @pytest.fixture
    def mock_tencent_vector_db_client(self):
        """Mock RPCVectorDBClient to avoid requiring actual TencentVectorDB instance."""
        with patch('mem0.vector_stores.tencent.RPCVectorDBClient') as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            yield mock_instance

    @pytest.fixture
    def tencent_vector_db(self, mock_tencent_vector_db_client):
        """Create TencentVectorDB instance with mocked client."""
        return TencentVectorDB(
            url="http://127.0.0.1:80",
            key="mock_tencent_api_key",
        )

    def test_initialization_with_int_dims(self, mock_tencent_vector_db_client):
        """Test that vector dimensions are correctly handled as integers."""
        db = TencentVectorDB(
            url="http://127.0.0.1:80",
            key="mock_tencent_api_key",
        )
        assert db.embedding_model_dims == 1536
        assert isinstance(db.embedding_model_dims, int)

    def test_batch_insert(self, tencent_vector_db, mock_tencent_vector_db_client):
        """Test that insert uses batch operation instead of loop (performance fix)."""
        ids = ["id1", "id2", "id3"]
        vectors = [[0.1] * 1536, [0.2] * 1536, [0.3] * 1536]
        payloads = [{"user_id": "alice"}, {"user_id": "bob"}, {"user_id": "charlie"}]

        tencent_vector_db.insert(ids=ids, vectors=vectors, payloads=payloads)

        # Verify insert was called once with all data (batch), not 3 times
        assert mock_tencent_vector_db_client.upsert.call_count == 1

        # Verify the data structure
        call_args = mock_tencent_vector_db_client.upsert.call_args
        inserted_data = call_args[1]['documents']

        assert len(inserted_data) == 3
        assert inserted_data[0]['id'] == 'id1'
        assert inserted_data[1]['id'] == 'id2'
        assert inserted_data[2]['id'] == 'id3'

    def test_create_filter_string_value(self, tencent_vector_db):
        """Test filter creation for string metadata values."""
        filters = {"user_id": "alice"}
        filter_str = tencent_vector_db._create_filter(filters)

        assert filter_str == 'metadata.user_id = "alice"'

    def test_create_filter_numeric_value(self, tencent_vector_db):
        """Test filter creation for numeric metadata values."""
        filters = {"age": 25}
        filter_str = tencent_vector_db._create_filter(filters)

        assert filter_str == 'metadata.age = 25'

    def test_create_filter_multiple_conditions(self, tencent_vector_db):
        """Test filter creation with multiple conditions."""
        filters = {"user_id": "alice", "category": "work"}
        filter_str = tencent_vector_db._create_filter(filters)

        # Should join with 'and'
        assert 'metadata.user_id = "alice"' in filter_str
        assert 'metadata.category = "work"' in filter_str
        assert ' and ' in filter_str

    def test_search_with_filters(self, tencent_vector_db, mock_tencent_vector_db_client):
        """Test search with metadata filters (reproduces user's bug scenario)."""
        # Setup mock return value
        mock_tencent_vector_db_client.search.return_value = [[
            {"id": "mem1", "score": 0.8, "metadata": {"user_id": "alice"}}
        ]]

        query_vector = [0.1] * 1536
        filters = {"user_id": "alice"}

        results = tencent_vector_db.search(
            query="test query",
            vectors=query_vector,
            limit=5,
            filters=filters
        )

        # Verify search was called with correct filter
        call_args = mock_tencent_vector_db_client.search.call_args
        assert call_args[1]['filter'] == 'metadata.user_id = "alice"'

        # Verify results are parsed correctly
        assert len(results) == 1
        assert results[0].id == "mem1"
        assert results[0].score == 0.8

    def test_search_different_user_ids(self, tencent_vector_db, mock_tencent_vector_db_client):
        """Test that search works with different user_ids (reproduces reported bug)."""
        # This test validates the fix for: "Error with different user_ids"

        # Mock return for first user
        mock_tencent_vector_db_client.search.return_value = [[
            {"id": "mem1", "score": 0.8, "metadata": {"user_id": "vdb_user"}}
        ]]

        results1 = tencent_vector_db.search("test", [0.1] * 1536, filters={"user_id": "vdb_user"})
        assert len(results1) == 1

        # Mock return for second user
        mock_tencent_vector_db_client.search.return_value = [[
            {"id": "mem2", "score": 0.8, "metadata": {"user_id": "bob"}}
        ]]

        # This should not raise "Unsupported Field type: 0" error
        results2 = tencent_vector_db.search("test", [0.2] * 1536, filters={"user_id": "bob"})
        assert len(results2) == 1

    def test_update(self, tencent_vector_db, mock_tencent_vector_db_client):
        """Test that update correctly uses upsert operation."""
        vector_id = "test_id"
        vector = [0.1] * 1536
        payload = {"user_id": "alice", "data": "Updated memory"}

        mock_tencent_vector_db_client.query.return_value = [
            {"id": "test_id", "metadata": {"user_id": "alice"}}
        ]

        tencent_vector_db.update(vector_id=vector_id, vector=vector, payload=payload)

        # Verify upsert was called (not delete+insert)
        mock_tencent_vector_db_client.update.assert_called_once()

        call_args = mock_tencent_vector_db_client.update.call_args
        assert call_args[1]['database_name'] == "mem0"
        assert call_args[1]['collection_name'] == "mem0"
        assert call_args[1]['document_ids'] == [vector_id]
        assert call_args[1]['data']['vector'] == vector
        assert call_args[1]['data']['metadata'] == {"user_id": "alice"}
        assert call_args[1]['data']['payload'] == {"data": "Updated memory"}

    def test_delete(self, tencent_vector_db, mock_tencent_vector_db_client):
        """Test vector deletion."""
        vector_id = "test_id"
        tencent_vector_db.delete(vector_id)

        mock_tencent_vector_db_client.delete.assert_called_once_with(
            database_name="mem0",
            collection_name="mem0",
            document_ids=[vector_id],
        )

    def test_get(self, tencent_vector_db, mock_tencent_vector_db_client):
        """Test retrieving a vector by ID."""
        vector_id = "test_id"
        mock_tencent_vector_db_client.query.return_value = [
            {"id": vector_id, "score": 0.6, "metadata": {"user_id": "alice"}}
        ]

        result = tencent_vector_db.get(vector_id)

        assert result.id == vector_id
        assert result.payload == {"user_id": "alice"}
        assert result.score == 0.6

    def test_list_with_filters(self, tencent_vector_db, mock_tencent_vector_db_client):
        """Test listing memories with filters."""
        mock_tencent_vector_db_client.query.return_value = [
            {"id": "mem1", "metadata": {"user_id": "alice"}},
            {"id": "mem2", "metadata": {"user_id": "alice"}}
        ]

        results = tencent_vector_db.list(filters={"user_id": "alice"}, limit=10)

        # Verify query was called with filter
        call_args = mock_tencent_vector_db_client.query.call_args
        assert call_args[1]['filter'] == 'metadata.user_id = "alice"'
        assert call_args[1]['limit'] == 10

        # Verify results
        assert len(results[0]) == 2

    def test_parse_output(self, tencent_vector_db):
        """Test output data parsing."""
        raw_data = [
            {
                "id": "mem1",
                "score": 0.9,
                "metadata": {"user_id": "alice"}
            },
            {
                "id": "mem2",
                "score": 0.85,
                "metadata": {"user_id": "bob"}
            }
        ]

        parsed = tencent_vector_db._parse_output(raw_data)

        assert len(parsed) == 2
        assert parsed[0].id == "mem1"
        assert parsed[0].score == 0.9
        assert parsed[0].payload == {"user_id": "alice"}
        assert parsed[1].id == "mem2"
        assert parsed[1].score == 0.85


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

