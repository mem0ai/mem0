import pytest
from unittest.mock import Mock, patch, MagicMock
from mem0.vector_stores.documentdb import DocumentDB, OutputData


class TestDocumentDB:
    @pytest.fixture
    def mock_mongo_client(self):
        with patch("mem0.vector_stores.documentdb.MongoClient") as mock_client:
            mock_db = Mock()
            mock_collection = Mock()
            
            # Create a mock client instance
            mock_client_instance = Mock()
            mock_client.return_value = mock_client_instance
            
            # Set up the client to return the mock database
            mock_client_instance.__getitem__ = Mock(return_value=mock_db)
            
            # Set up the database to return the mock collection
            mock_db.__getitem__ = Mock(return_value=mock_collection)
            mock_db.list_collection_names = Mock(return_value=[])
            
            # Set up collection methods
            mock_collection.list_indexes = Mock(return_value=[])
            mock_collection.insert_one = Mock()
            mock_collection.delete_one = Mock()
            mock_collection.create_index = Mock()
            
            yield mock_client, mock_db, mock_collection

    @pytest.fixture
    def documentdb_instance(self, mock_mongo_client):
        mock_client, mock_db, mock_collection = mock_mongo_client
        with patch.object(DocumentDB, 'create_col', return_value=mock_collection):
            return DocumentDB(
                db_name="test_db",
                collection_name="test_collection",
                embedding_model_dims=768,
                mongo_uri="mongodb://test:test@localhost:27017"
            )

    def test_init(self, documentdb_instance):
        assert documentdb_instance.db_name == "test_db"
        assert documentdb_instance.collection_name == "test_collection"
        assert documentdb_instance.embedding_model_dims == 768

    def test_insert(self, documentdb_instance):
        vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        payloads = [{"text": "test1"}, {"text": "test2"}]
        ids = ["id1", "id2"]

        documentdb_instance.collection.insert_many = Mock()
        documentdb_instance.insert(vectors, payloads, ids)
        
        documentdb_instance.collection.insert_many.assert_called_once()
        call_args = documentdb_instance.collection.insert_many.call_args[0][0]
        assert len(call_args) == 2
        assert call_args[0]["_id"] == "id1"
        assert call_args[0]["vectorEmbedding"] == [0.1, 0.2, 0.3]
        assert call_args[0]["payload"] == {"text": "test1"}

    def test_search(self, documentdb_instance):
        # Mock the collection and its methods
        mock_results = [
            {"_id": "id1", "payload": {"text": "test1"}},
            {"_id": "id2", "payload": {"text": "test2"}}
        ]
        
        documentdb_instance.collection.list_indexes.return_value = [{"name": "test_collection_vector_index"}]
        documentdb_instance.collection.aggregate.return_value = mock_results
        documentdb_instance.client.__getitem__.return_value.__getitem__.return_value = documentdb_instance.collection

        query_vector = [0.1, 0.2, 0.3]
        results = documentdb_instance.search("test query", query_vector, limit=2)

        assert len(results) == 2
        assert isinstance(results[0], OutputData)
        assert results[0].id == "id1"
        assert results[0].payload == {"text": "test1"}
        assert results[0].score == 1.0  # First result gets highest score

    def test_delete(self, documentdb_instance):
        documentdb_instance.collection.delete_one = Mock()
        documentdb_instance.collection.delete_one.return_value.deleted_count = 1
        
        documentdb_instance.delete("test_id")
        documentdb_instance.collection.delete_one.assert_called_once_with({"_id": "test_id"})

    def test_update(self, documentdb_instance):
        documentdb_instance.collection.update_one = Mock()
        documentdb_instance.collection.update_one.return_value.matched_count = 1
        
        new_vector = [0.7, 0.8, 0.9]
        new_payload = {"text": "updated"}
        
        documentdb_instance.update("test_id", vector=new_vector, payload=new_payload)
        
        expected_update = {"$set": {"vectorEmbedding": new_vector, "payload": new_payload}}
        documentdb_instance.collection.update_one.assert_called_once_with({"_id": "test_id"}, expected_update)

    def test_get(self, documentdb_instance):
        mock_doc = {"_id": "test_id", "payload": {"text": "test"}}
        documentdb_instance.collection.find_one = Mock(return_value=mock_doc)
        
        result = documentdb_instance.get("test_id")
        
        assert isinstance(result, OutputData)
        assert result.id == "test_id"
        assert result.payload == {"text": "test"}
        documentdb_instance.collection.find_one.assert_called_once_with({"_id": "test_id"})

    def test_list_cols(self, documentdb_instance):
        documentdb_instance.db.list_collection_names = Mock(return_value=["col1", "col2"])
        
        collections = documentdb_instance.list_cols()
        
        assert collections == ["col1", "col2"]
        documentdb_instance.db.list_collection_names.assert_called_once()

    def test_list(self, documentdb_instance):
        mock_docs = [
            {"_id": "id1", "payload": {"text": "test1"}},
            {"_id": "id2", "payload": {"text": "test2"}}
        ]
        
        mock_cursor = Mock()
        mock_cursor.__iter__ = Mock(return_value=iter(mock_docs))
        documentdb_instance.collection.find.return_value.limit.return_value = mock_cursor
        
        results = documentdb_instance.list(limit=2)
        
        assert len(results) == 2
        assert isinstance(results[0], OutputData)
        assert results[0].id == "id1"
        assert results[0].payload == {"text": "test1"}