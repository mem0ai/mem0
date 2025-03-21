import unittest
import uuid
from unittest.mock import MagicMock, patch

from couchbase.bucket import Bucket
from couchbase.cluster import Cluster
from couchbase.collection import Collection
from couchbase.management.search import SearchIndex
from couchbase.result import GetResult, QueryResult
from couchbase.scope import Scope
from couchbase.search import SearchRow

from mem0.vector_stores.couchbase import Couchbase


class TestCouchbaseVectorStore(unittest.TestCase):  
    def setUp(self):  
        self.cluster_mock = MagicMock(spec=Cluster)  
        self.bucket_mock = MagicMock(spec=Bucket)  
        self.scope_mock = MagicMock(spec=Scope)  
        self.collection_mock = MagicMock(spec=Collection)  

        self.bucket_mock.name = "test_bucket"
        self.scope_mock.name = "test_scope"

        self.cluster_mock.bucket.return_value = self.bucket_mock  
        self.bucket_mock.scope.return_value = self.scope_mock  
        self.scope_mock.collection.return_value = self.collection_mock  

        self.cluster_patcher = patch('mem0.vector_stores.couchbase.Cluster', return_value=self.cluster_mock)
        self.cluster_patcher.start()
        
        self.vector_store = Couchbase(  
            embedding_model_dims=128,  
            connection_str="couchbase://localhost",  
            username="Administrator",  
            password="password",  
            bucket_name="test_bucket",  
            scope_name="test_scope",  
            embedding_key="embedding",  
        )  

    def test_insert(self):  
        vectors = [[0.1, 0.2], [0.3, 0.4]]  
        payloads = [{"key": "value1"}, {"key": "value2"}]  
        ids = [str(uuid.uuid4()), str(uuid.uuid4())]  

        self.vector_store.insert(vectors=vectors, payloads=payloads, ids=ids)  

        expected_docs = {  
            ids[0]: {"embedding": vectors[0], "payload": payloads[0]},  
            ids[1]: {"embedding": vectors[1], "payload": payloads[1]},  
        }  
        self.collection_mock.upsert_multi.assert_called_once_with(expected_docs)  

    def test_create_search_index(self):
        search_index_manager_mock = MagicMock()
        self.scope_mock.search_indexes.return_value = search_index_manager_mock
        
        collection_name = "test_collection"
        index_name = "test_collection_index"
        vector_size = 128
        distance = "cosine"
        
        with patch('mem0.vector_stores.couchbase.json.dumps') as mock_dumps:
            mock_dumps.return_value = '{"mocked_index_definition": true}'
            with patch('mem0.vector_stores.couchbase.SearchIndex.from_json') as mock_from_json:
                mock_from_json.return_value = MagicMock(spec=SearchIndex)
                self.vector_store.create_search_index(collection_name, index_name, vector_size, distance)
                
                mock_from_json.assert_called_once_with('{"mocked_index_definition": true}')
                
                search_index_manager_mock.upsert_index.assert_called_once()
    
    def test_create_col(self):
        collection_name = "new_collection"
        vector_size = 128
        distance = "dot_product"
        
        with patch.object(self.vector_store, 'create_search_index') as mock_create_index:
            mock_create_index.return_value = None
            self.cluster_mock.query.side_effect = None  # Reset any previous side effect
            
            result = self.vector_store.create_col(collection_name, vector_size, distance)
            
            self.cluster_mock.query.assert_any_call(f"CREATE COLLECTION {self.bucket_mock.name}.{self.scope_mock.name}.{collection_name}")
            self.cluster_mock.query.assert_any_call(f"CREATE PRIMARY INDEX ON {self.bucket_mock.name}.{self.scope_mock.name}.{collection_name}")
            
            mock_create_index.assert_called_once_with(collection_name, f"{collection_name}_index", vector_size, distance)
            
            self.assertTrue(result)
            
            self.cluster_mock.reset_mock()
            mock_create_index.reset_mock()
            
            self.cluster_mock.query.side_effect = Exception("Test error")
            
            result = self.vector_store.create_col(collection_name, vector_size, distance)
            
            self.assertFalse(result)

    def test_search(self):  
        query_vector = [0.1, 0.2]  
        mock_search_result = MagicMock()  
        mock_search_row = MagicMock(spec=SearchRow)  
        mock_search_row.id = "vector_1"  
        mock_search_row.score = 0.95
        mock_search_row.fields = {
            "embedding": query_vector,
            "payload.key": "value"
        }  
        mock_search_result.rows.return_value = [mock_search_row]  

        self.scope_mock.search.return_value = mock_search_result  

        results = self.vector_store.search(query=query_vector, limit=1)  

        self.scope_mock.search.assert_called_once()  
        self.assertEqual(len(results), 1)  
        self.assertEqual(results[0].id, "vector_1")  
        self.assertEqual(results[0].score, 0.95)
        self.assertEqual(results[0].payload, {"key": "value"})  

    def test_delete(self):  
        doc_id = "vector_1"  
        self.vector_store.delete(doc_id=doc_id)  
        self.collection_mock.remove.assert_called_once_with(doc_id)  

    def test_update(self):  
        doc_id = "vector_1"  
        updated_vector = [0.2, 0.3]  
        updated_payload = {"key": "updated_value"}  

        mock_get_result = MagicMock(spec=GetResult)  
        mock_content = {  
            "embedding": [0.1, 0.2],  
            "payload": {"key": "value"},  
        }
        mock_get_result.content_as = {dict: mock_content}
        self.collection_mock.get.return_value = mock_get_result  
        self.vector_store.update(doc_id=doc_id, vector=updated_vector, payload=updated_payload)  
        expected_doc = {"embedding": updated_vector, "payload": updated_payload}  
        self.collection_mock.upsert.assert_called_once_with(doc_id, expected_doc)  

    def test_get(self):  
        doc_id = "vector_1"  

        mock_get_result = MagicMock(spec=GetResult)  
        mock_content = {  
            "embedding": [0.1, 0.2],  
            "payload": {"key": "value"},  
        }
        mock_get_result.content_as = {dict: mock_content}
        self.collection_mock.get.return_value = mock_get_result  
        result = self.vector_store.get(doc_id=doc_id)  

        self.collection_mock.get.assert_called_once_with(doc_id)  
        self.assertEqual(result["embedding"], [0.1, 0.2])  
        self.assertEqual(result["payload"], {"key": "value"})  

    def test_list(self):  
        mock_query_result = MagicMock(spec=QueryResult)  
        mock_row = MagicMock()
        mock_row.id = "vector_1"
        mock_query_result.rows.return_value = [mock_row]  
        self.cluster_mock.query.return_value = mock_query_result  

        mock_get_result = MagicMock(spec=GetResult)
        mock_content = {
            "embedding": [0.1, 0.2],
            "payload": {"key": "value"}
        }
        mock_get_result.content_as = {dict: mock_content}
        self.collection_mock.get.return_value = mock_get_result

        results = self.vector_store.list(limit=1)  

        self.cluster_mock.query.assert_called_once()  
        self.assertEqual(len(results), 1)  
        self.assertEqual(results[0]["id"], "vector_1")  
        self.assertEqual(results[0]["embedding"], [0.1, 0.2])  
        self.assertEqual(results[0]["payload"], {"key": "value"})  

    def test_list_cols(self):  
        mock_collections = MagicMock()
        mock_scope = MagicMock()
        mock_scope.name = self.scope_mock.name
        mock_collection = MagicMock()
        mock_collection.name = "test_collection"
        mock_scope.collections = [mock_collection]
        mock_collections.get_all_scopes.return_value = [mock_scope]
        self.bucket_mock.collections.return_value = mock_collections
        
        result = self.vector_store.list_cols()
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "test_collection")

    def test_delete_col(self):  
        collection_name = "test_collection"
        self.vector_store.delete_col(name=collection_name)
        
        expected_query = f"DROP COLLECTION {self.bucket_mock.name}.{self.scope_mock.name}.{collection_name}"
        self.cluster_mock.query.assert_called_once_with(expected_query)

    def test_col_info(self):  
        self.scope_mock.collection.reset_mock()
        
        result = self.vector_store.col_info(name="test_collection")  
        self.assertIsInstance(result, Collection)
        self.scope_mock.collection.assert_called_once_with("test_collection")

    def tearDown(self):
        self.cluster_patcher.stop()
        del self.vector_store


if __name__ == "__main__":  
    unittest.main()  