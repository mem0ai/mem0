import unittest

try:
    from elasticsearch import Elasticsearch
    from elasticsearch.helpers import bulk
except ImportError:
    raise ImportError(
        "Elasticsearch requires extra dependencies. Install with `pip install --upgrade embedchain[elasticsearch]`"
    ) from None

from embedchain.config import ElasticsearchDBConfig
from embedchain.vectordb.elasticsearch_db import ElasticsearchDB

class TestElasticsearchDB(unittest.TestCase):

    def setUp(self):
        self.es_config = ElasticsearchDBConfig(ES_URL="http://localhost:9200")
        self.db = ElasticsearchDB(config=self.es_config)

    def tearDown(self):
        # Clean up any test data in Elasticsearch
        if self.db.client.indices.exists(index=self.db._get_index()):
            self.db.client.indices.delete(index=self.db._get_index())

    def test_initialize(self):
        # Ensure that the Elasticsearch index is created during initialization
        self.assertTrue(self.db.client.indices.exists(index=self.db._get_index()))

    def test_add_and_get(self):
        # Add documents to the database and then retrieve them
        documents = ["document1", "document2", "document3"]
        metadatas = [{"app_id": "app1"}, {"app_id": "app2"}, {"app_id": "app1"}]
        ids = ["1", "2", "3"]
        self.db.add(documents, metadatas, ids)

        # Test getting documents by IDs
        retrieved_ids = self.db.get(ids=ids)["ids"]
        self.assertEqual(retrieved_ids, set(ids))

        # Test getting documents by metadata
        retrieved_ids = self.db.get(where={"app_id": "app1"})["ids"]
        self.assertEqual(retrieved_ids, {"1", "3"})

    def test_query(self):
        # Add documents to the database
        documents = ["document1", "document2", "document3"]
        metadatas = [{"app_id": "app1"}, {"app_id": "app2"}, {"app_id": "app1"}]
        ids = ["1", "2", "3"]
        self.db.add(documents, metadatas, ids)

        # Perform a query
        input_query = ["query"]
        where = {"app_id": "app1"}
        n_results = 2
        results = self.db.query(input_query, n_results, where)
        
        # Ensure that the results are a list of strings
        self.assertIsInstance(results, list)
        self.assertTrue(all(isinstance(result, str) for result in results))
    
    def test_count(self):
        # Add documents to the database
        documents = ["document1", "document2", "document3"]
        metadatas = [{"app_id": "app1"}, {"app_id": "app2"}, {"app_id": "app1"}]
        ids = ["1", "2", "3"]
        self.db.add(documents, metadatas, ids)

        # Check the count of documents
        count = self.db.count()
        self.assertEqual(count, 3)

    def test_reset(self):
        # Add documents to the database
        documents = ["document1", "document2", "document3"]
        metadatas = [{"app_id": "app1"}, {"app_id": "app2"}, {"app_id": "app1"}]
        ids = ["1", "2", "3"]
        self.db.add(documents, metadatas, ids)

        # Reset the database
        self.db.reset()

        # Check that the Elasticsearch index no longer exists
        self.assertFalse(self.db.client.indices.exists(index=self.db._get_index()))

if __name__ == '__main__':
    unittest.main()
