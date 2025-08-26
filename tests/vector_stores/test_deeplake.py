import uuid
from collections import defaultdict
from unittest.mock import MagicMock, Mock, patch
import pytest
from mem0.vector_stores.deeplake import DeepLake


@pytest.fixture
def mock_deeplake():
    """Mock the deeplake module and its components"""
    with patch("mem0.vector_stores.deeplake.deeplake") as mock_dl:
        # Mock deeplake module methods
        mock_dl.exists.return_value = False
        mock_dl.types.Text.return_value = "text_type"
        mock_dl.types.Embedding.return_value = "embedding_type"
        mock_dl.types.Dict.return_value = "dict_type" 
        mock_dl.IndexingMode.Always = "always"
        mock_dl.types.QuantizationType.Binary = "binary"
        
        # Mock client instance
        mock_client = Mock()
        mock_dl.create.return_value = mock_client
        mock_dl.open.return_value = mock_client
        
        yield mock_dl, mock_client


@pytest.fixture
def deeplake_instance(mock_deeplake):
    """Create a DeepLake instance with mocked dependencies"""
    mock_dl, mock_client = mock_deeplake
    
    # Create instance with test parameters (no need to patch imports anymore)
    instance = DeepLake(
        url="mem://test-collection",
        embedding_model_dims=384,
        quantize=False
    )
    
    yield instance, mock_client


class TestDeepLakeInit:
    """Test DeepLake initialization"""
    
    def test_init_new_collection(self, mock_deeplake):
        """Test initialization of new collection"""
        mock_dl, mock_client = mock_deeplake
        mock_dl.exists.return_value = False
        
        instance = DeepLake(
            url="mem://test-new",
            embedding_model_dims=768,
            quantize=True,
            creds={"key": "value"},
            token="test-token"
        )
        
        # Verify collection creation
        mock_dl.create.assert_called_once()
        call_args = mock_dl.create.call_args
        assert call_args[0][0] == "mem://test-new"
        assert call_args[1]["creds"] == {"key": "value"}
        assert call_args[1]["token"] == "test-token"
        
        # Verify schema structure
        schema = call_args[1]["schema"]
        assert "id" in schema
        assert "user_id" in schema
        assert "run_id" in schema
        assert "agent_id" in schema
        assert "vector" in schema
        assert "payload" in schema
        
        # Verify instance attributes
        assert instance.url == "mem://test-new"
        assert instance.embedding_model_dims == 768
        assert instance.quantize is True
        assert instance.creds == {"key": "value"}
        assert instance.token == "test-token"
    
    def test_init_existing_collection(self, mock_deeplake):
        """Test initialization with existing collection"""
        mock_dl, mock_client = mock_deeplake
        mock_dl.exists.return_value = True
        
        instance = DeepLake(
            url="mem://existing-collection", 
            embedding_model_dims=512
        )
        
        # Should open existing collection, not create new one
        mock_dl.open.assert_called_once_with(
            "mem://existing-collection", 
            creds=None, 
            token=None
        )
        mock_dl.create.assert_not_called()


class TestDeepLakeInsert:
    """Test vector insertion functionality"""
    
    def test_insert_basic(self, deeplake_instance):
        """Test basic vector insertion"""
        instance, mock_client = deeplake_instance
        
        vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        payloads = [{"data": "test1"}, {"data": "test2"}]
        ids = ["id1", "id2"]
        
        instance.insert(vectors=vectors, payloads=payloads, ids=ids)
        
        # Verify append was called with correct structure
        mock_client.append.assert_called_once()
        call_args = mock_client.append.call_args[0][0]
        
        assert call_args["id"] == ["id1", "id2"]
        assert call_args["vector"] == vectors
        assert call_args["payload"] == payloads
    
    def test_insert_without_ids(self, deeplake_instance):
        """Test insertion without providing IDs (should auto-generate)"""
        instance, mock_client = deeplake_instance
        
        # Mock uuid.uuid4() properly
        with patch("mem0.vector_stores.deeplake.uuid.uuid4") as mock_uuid:
            mock_uuid.side_effect = ["auto-id-1", "auto-id-2"]
            
            vectors = [[0.1, 0.2], [0.3, 0.4]]
            payloads = [{"test": "data1"}, {"test": "data2"}]
            
            instance.insert(vectors=vectors, payloads=payloads)
            
            call_args = mock_client.append.call_args[0][0]
            assert call_args["id"] == ["auto-id-1", "auto-id-2"]
    
    def test_insert_without_payloads(self, deeplake_instance):
        """Test insertion without payloads (should create empty dicts)"""
        instance, mock_client = deeplake_instance
        
        vectors = [[0.1, 0.2]]
        ids = ["test-id"]
        
        instance.insert(vectors=vectors, ids=ids)
        
        call_args = mock_client.append.call_args[0][0]
        assert call_args["payload"] == [{}]
    
    def test_insert_with_metadata_fields(self, deeplake_instance):
        """Test insertion with user_id, agent_id, run_id in payloads"""
        instance, mock_client = deeplake_instance
        
        vectors = [[0.1, 0.2], [0.3, 0.4]]
        payloads = [
            {"data": "test1", "user_id": "user1", "agent_id": "agent1"},
            {"data": "test2", "run_id": "run1"}
        ]
        ids = ["id1", "id2"]
        
        instance.insert(vectors=vectors, payloads=payloads, ids=ids)
        
        call_args = mock_client.append.call_args[0][0]
        
        # Verify metadata fields are extracted correctly
        assert call_args["user_id"] == ["user1", ""]
        assert call_args["agent_id"] == ["agent1", ""]
        assert call_args["run_id"] == ["", "run1"]


class TestDeepLakeSearch:
    """Test vector search functionality"""
    
    def test_search_basic(self, deeplake_instance):
        """Test basic vector search"""
        instance, mock_client = deeplake_instance
        
        # Create proper mock that behaves like a list-containing dict
        class MockQueryResult(dict):
            def __len__(self):
                return 2
                
        mock_result = MockQueryResult({
            "id": ["id1", "id2"],
            "payload": [{"data": "test1"}, {"data": "test2"}],
            "score": [0.9, 0.8]
        })
        mock_client.query.return_value = mock_result
        
        vectors = [0.1, 0.2, 0.3]
        results = instance.search(query="test", vectors=vectors, limit=2)
        
        # Verify query was called with correct SQL
        mock_client.query.assert_called_once()
        query_sql = mock_client.query.call_args[0][0]
        assert "SELECT *" in query_sql
        assert "ORDER BY COSINE_SIMILARITY" in query_sql
        assert "LIMIT 2" in query_sql
        
        # Verify results structure
        assert len(results) == 2
        assert results[0].id == "id1"
        assert results[0].payload == {"data": "test1"}
        assert results[0].score == 0.9
    
    def test_search_with_filters(self, deeplake_instance):
        """Test search with filters"""
        instance, mock_client = deeplake_instance
        
        class MockQueryResult(dict):
            def __len__(self):
                return 1
                
        mock_result = MockQueryResult({
            "id": ["id1"],
            "payload": [{"data": "test1"}],
            "score": [0.9]
        })
        mock_client.query.return_value = mock_result
        
        with patch.object(instance, '_build_filter_expression') as mock_filter:
            mock_filter.return_value = "sanitized_key = 'test'"
            
            filters = {"user_id": "test"}
            results = instance.search(
                query="test", 
                vectors=[0.1, 0.2], 
                filters=filters
            )
            
            # Verify filter expression was built
            mock_filter.assert_called_once_with(filters)
            
            # Verify WHERE clause was included in query
            query_sql = mock_client.query.call_args[0][0]
            assert "WHERE sanitized_key = 'test'" in query_sql
    
    def test_search_no_results(self, deeplake_instance):
        """Test search with no results"""
        instance, mock_client = deeplake_instance
        
        # Mock empty result
        class MockEmptyResult(dict):
            def __len__(self):
                return 0
                
        mock_result = MockEmptyResult()
        mock_client.query.return_value = mock_result
        
        results = instance.search(query="test", vectors=[0.1, 0.2])
        
        assert results == []
    
    def test_build_filter_expression(self, deeplake_instance):
        """Test filter expression building"""
        instance, mock_client = deeplake_instance
        
        with patch.object(instance, '_sanitize_key') as mock_sanitize:
            mock_sanitize.side_effect = lambda x: f"clean_{x}"
            
            # Test string value
            filters = {"user_id": "test'user", "count": 5}
            result = instance._build_filter_expression(filters)
            
            # Should handle string escaping and numeric values
            assert "clean_user_id = 'test''user'" in result
            assert "clean_count = 5" in result
            assert " AND " in result


class TestDeepLakeDelete:
    """Test vector deletion functionality"""
    
    def test_delete_existing_vector(self, deeplake_instance):
        """Test deleting an existing vector"""
        instance, mock_client = deeplake_instance
        
        # Mock query to find vector
        mock_client.query.return_value = {
            "row_id": [5, 10]  # Multiple matches
        }
        
        instance.delete("test-id")
        
        # Verify query was called to find vector
        query_sql = mock_client.query.call_args[0][0]
        assert "WHERE id = 'test-id'" in query_sql
        assert "ROW_NUMBER() as row_id" in query_sql
        
        # Verify delete was called for each row (in reverse order)
        expected_calls = [((10,),), ((5,),)]
        assert mock_client.delete.call_args_list == expected_calls
        mock_client.commit.assert_called_once()
    
    def test_delete_nonexistent_vector(self, deeplake_instance):
        """Test deleting a non-existent vector"""
        instance, mock_client = deeplake_instance
        
        # Mock empty query result
        class MockEmptyResult(dict):
            def __len__(self):
                return 0
                
        mock_result = MockEmptyResult({"row_id": []})
        mock_client.query.return_value = mock_result
        
        instance.delete("nonexistent-id")
        
        # Should not call delete or commit
        mock_client.delete.assert_not_called()
        mock_client.commit.assert_not_called()


class TestDeepLakeUpdate:
    """Test vector update functionality"""
    
    def test_update_vector_and_payload(self, deeplake_instance):
        """Test updating both vector and payload"""
        instance, mock_client = deeplake_instance
        
        # Mock query to find vector
        mock_client.query.return_value = {"row_id": [3]}
        mock_client.__getitem__ = Mock(return_value={"vector": Mock(), "payload": Mock()})
        
        new_vector = [0.7, 0.8, 0.9]
        new_payload = {"updated": "data"}
        
        instance.update("test-id", vector=new_vector, payload=new_payload)
        
        # Verify both vector and payload were updated
        mock_client.commit.assert_called_once()
    
    def test_update_vector_only(self, deeplake_instance):
        """Test updating only the vector"""
        instance, mock_client = deeplake_instance
        mock_client.query.return_value = {"row_id": [3]}
        mock_client.__getitem__ = Mock(return_value={"vector": Mock(), "payload": Mock()})
        
        new_vector = [0.7, 0.8, 0.9]
        instance.update("test-id", vector=new_vector)
        
        mock_client.commit.assert_called_once()
    
    def test_update_nonexistent_vector(self, deeplake_instance):
        """Test updating a non-existent vector"""
        instance, mock_client = deeplake_instance
        
        # Mock empty query result
        class MockEmptyResult(dict):
            def __len__(self):
                return 0
                
        mock_result = MockEmptyResult({"row_id": []})
        mock_client.query.return_value = mock_result
        
        instance.update("nonexistent-id", vector=[0.1, 0.2])
        
        # Should not call commit
        mock_client.commit.assert_not_called()


class TestDeepLakeGet:
    """Test vector retrieval functionality"""
    
    def test_get_existing_vector(self, deeplake_instance):
        """Test getting an existing vector"""
        instance, mock_client = deeplake_instance
        
        # Mock the correct response structure 
        mock_client.query.return_value = {
            "id": ["test-id"],
            "payload": [{"data": "test"}]
        }
        
        result = instance.get("test-id")
        
        # Verify query was called correctly
        query_sql = mock_client.query.call_args[0][0]
        assert "WHERE id = 'test-id'" in query_sql
        
        # Verify result structure
        assert result.id == "test-id"
        assert result.payload == {"data": "test"}
        assert result.score is None
    
    def test_get_nonexistent_vector(self, deeplake_instance):
        """Test getting a non-existent vector"""
        instance, mock_client = deeplake_instance
        
        # Mock empty query result
        mock_client.query.return_value = {}
        
        result = instance.get("nonexistent-id")
        
        # Should return None for non-existent vectors
        assert result is None


class TestDeepLakeList:
    """Test vector listing functionality"""
    
    def test_list_all_vectors(self, deeplake_instance):
        """Test listing all vectors"""
        instance, mock_client = deeplake_instance
        
        mock_client.query.return_value = {
            "id": ["id1", "id2"],
            "payload": [{"data": "test1"}, {"data": "test2"}]
        }
        
        results = instance.list(limit=100)
        
        # Verify query structure
        query_sql = mock_client.query.call_args[0][0]
        assert "SELECT *" in query_sql
        assert "LIMIT 100" in query_sql
        
        # Verify results structure (wrapped in extra array)
        assert len(results) == 1
        assert len(results[0]) == 2
        assert results[0][0].id == "id1"
        assert results[0][1].id == "id2"
    
    def test_list_with_filters(self, deeplake_instance):
        """Test listing with filters"""
        instance, mock_client = deeplake_instance
        
        class MockQueryResult(dict):
            def __len__(self):
                return 1
                
        mock_result = MockQueryResult({
            "id": ["id1"],
            "payload": [{"data": "test1"}]
        })
        mock_client.query.return_value = mock_result
        
        with patch.object(instance, '_build_filter_expression') as mock_filter:
            mock_filter.return_value = "user_id = 'test'"
            
            filters = {"user_id": "test"}
            results = instance.list(filters=filters, limit=50)
            
            # Verify filter was applied
            mock_filter.assert_called_once_with(filters)
            query_sql = mock_client.query.call_args[0][0]
            assert "WHERE user_id = 'test'" in query_sql
    
    def test_list_empty_results(self, deeplake_instance):
        """Test listing with no results"""
        instance, mock_client = deeplake_instance
        mock_client.query.return_value = {}
        
        results = instance.list()
        
        # Should return empty list wrapped in array
        assert results == [[]]


class TestDeepLakeUtility:
    """Test utility methods"""
    
    def test_sanitize_key(self, deeplake_instance):
        """Test key sanitization"""
        instance, mock_client = deeplake_instance
        
        # Test actual functionality since re is now imported
        result = instance._sanitize_key("test-key!@#")
        
        # Should remove non-word characters
        assert result == "testkey"
    
    def test_collection_exists(self, deeplake_instance):
        """Test collection existence check"""
        instance, mock_client = deeplake_instance
        
        with patch("mem0.vector_stores.deeplake.deeplake") as mock_dl:
            mock_dl.exists.return_value = True
            
            result = instance._collection_exists()
            
            mock_dl.exists.assert_called_once_with(
                instance.url,
                creds=instance.creds,
                token=instance.token
            )
            assert result is True
    
    def test_col_info(self, deeplake_instance):
        """Test collection info"""
        instance, mock_client = deeplake_instance
        
        info = instance.col_info()
        
        assert info == {"url": "mem://test-collection"}
    
    def test_list_cols(self, deeplake_instance):
        """Test listing collections"""
        instance, mock_client = deeplake_instance
        
        cols = instance.list_cols()
        
        assert cols == ["mem://test-collection"]
    
    def test_operations_not_supported(self, deeplake_instance):
        """Test operations that are not supported"""
        instance, mock_client = deeplake_instance
        
        # These should not raise exceptions but log warnings
        instance.delete_col()
        instance.reset()
        
        # No assertions needed, just verify they don't crash


class TestDeepLakeIntegration:
    """Integration-style tests"""
    
    @patch("mem0.vector_stores.deeplake.deeplake")
    def test_full_lifecycle(self, mock_deeplake_module):
        """Test full vector lifecycle: insert, search, update, delete"""
        # Setup mocks
        mock_client = Mock()
        mock_deeplake_module.exists.return_value = False
        mock_deeplake_module.create.return_value = mock_client
        mock_deeplake_module.types.Text.return_value = "text"
        mock_deeplake_module.types.Embedding.return_value = "embedding"
        mock_deeplake_module.types.Dict.return_value = "dict"
        mock_deeplake_module.IndexingMode.Always = "always"
        
        # Create instance (no need to patch imports)
        instance = DeepLake(
            url="mem://lifecycle-test",
            embedding_model_dims=256
        )
        
        # Test insert
        instance.insert(
            vectors=[[0.1, 0.2]], 
            payloads=[{"test": "data"}], 
            ids=["test-id"]
        )
        mock_client.append.assert_called_once()
        
        # Test search
        class MockQueryResult(dict):
            def __len__(self):
                return 1
                
        search_result = MockQueryResult({
            "id": ["test-id"],
            "payload": [{"test": "data"}],
            "score": [0.95]
        })
        mock_client.query.return_value = search_result
        
        results = instance.search("test", [0.1, 0.2])
        assert len(results) == 1
        assert results[0].id == "test-id"
        
        # Test update
        mock_client.query.return_value = {"row_id": [0]}
        mock_client.__getitem__ = Mock(return_value={
            "vector": Mock(), 
            "payload": Mock()
        })
        
        instance.update("test-id", payload={"updated": "data"})
        mock_client.commit.assert_called()
        
        # Test delete
        mock_client.query.return_value = {"row_id": [0]}
        instance.delete("test-id")
        mock_client.delete.assert_called_with(0)


if __name__ == "__main__":
    pytest.main([__file__])
