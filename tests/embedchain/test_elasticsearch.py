import unittest
from unittest.mock import Mock


from elasticsearch import Elasticsearch
from embedchain.config import ElasticsearchDBConfig
from embedchain.vectordb.elasticsearch import ElasticsearchDB


class TestElasticsearchDB(unittest.TestCase):


    def setUp(self):
        self.mock_es = Mock(spec=Elasticsearch)
        self.mock_es.indices = Mock()
        # Initialize ElasticsearchDBConfig with the correct ES_URL
        self.config = ElasticsearchDBConfig(es_url="http://localhost:9200")
        self.db = ElasticsearchDB(config=self.config)
        self.db.client = self.mock_es

        # Mock the embedder attribute
        self.db.embedder = Mock()  # You may need to configure the mock further if necessary


    def tearDown(self):
    # Reset mock after each test
        self.mock_es.reset_mock()
        
    def test_initialize(self):
        # Ensure that the Elasticsearch index is created during initialization
        self.mock_es.indices.exists.return_value = False
        self.db._initialize()
        self.mock_es.indices.create.assert_called_with(
            index=self.db._get_index(),
            body={
                "mappings": {
                    "properties": {
                        "text": {"type": "text"},
                        "embeddings": {"type": "dense_vector", "index": False, "dims": 300},  
                    }
                }
            }
        )

    def test_get_or_create_db(self):
        # Test that _get_or_create_db returns the client
        result = self.db._get_or_create_db()
        self.assertEqual(result, self.mock_es)

    def test_get_or_create_collection(self):
        # Test that _get_or_create_collection returns None and does not call Elasticsearch
        result = self.db._get_or_create_collection("collection_name")
        self.assertIsNone(result)
        self.mock_es.indices.create.assert_not_called()

    def test_add(self):
        self.mock_es.bulk.return_value = None

        # Call the `add()` method.
        self.db.add(
            ["document1", "document2", "document3"],
            ["metadata1", "metadata2", "metadata3"],
            ["1", "2", "3"])

        self.db.embedder.embedding_fn.return_value = ["embedding1", "embedding2", "embedding3"]
        # Assert that the Elasticsearch client was called with the expected arguments.
        self.mock_es.bulk.assert_called_once_with([
            {
                "_index": self.db._get_index(),
                "_id": "1",
                "_source": {"text": "document1", "metadata": "metadata1", "embeddings": "embedding1"},
            },
            {
                "_index": self.db._get_index(),
                "_id": "2",
                "_source": {"text": "document2", "metadata": "metadata2", "embeddings": "embedding2"},
            },
            {
                "_index": self.db._get_index(),
                "_id": "3",
                "_source": {"text": "document3", "metadata": "metadata3", "embeddings": "embedding3"},
            },
        ])


    def test_query(self):
        # Test the query method
        input_query = ["query"]
        where = {"app_id": "app1"}
        n_results = 2
        self.db.embedder.embedding_fn.return_value = ["embedding1"]  # Adjust as needed
        self.mock_es.search.return_value = {
            "hits": {
                "hits": [
                    {"_source": {"text": "result1"}},
                    {"_source": {"text": "result2"}},
                ]
            }
        }

        results = self.db.query(input_query, n_results, where)

        self.assertEqual(results, ["result1", "result2"])
        self.mock_es.search.assert_called_once_with(
            index=self.db._get_index(),
            query={
                "script_score": {
                    "query": {"bool": {"must": [{"exists": {"field": "text"}}]}},
                    "script": {
                        "source": "cosineSimilarity(params.input_query_vector, 'embeddings') + 1.0",
                        "params": {"input_query_vector": "query"},  # Use the provided query directly
                    },
                }
            },
            _source=["text"],
            size=n_results,
        )

    def test_set_collection_name(self):
        # Test the set_collection_name method
        self.db.set_collection_name("new_collection")
        self.assertEqual(self.db.config.collection_name, "new_collection")

    def test_count(self):
        # Test the count method
        self.mock_es.count.return_value = {"count": 42}
        count = self.db.count()
        self.assertEqual(count, 42)
        self.mock_es.count.assert_called_once_with(index=self.db._get_index(), query={"match_all": {}})

    def reset(self):
        """
        Resets the database. Deletes all embeddings irreversibly.
        """
        # Delete all data from the database
        if self.client.indices.exists(index=self._get_index()):
            # delete index in Es
            self.client.indices.delete(index=self._get_index())
            

    def test_get_index(self):
        # Test the _get_index method
        self.db.config.collection_name = "test_collection"
        self.db.embedder.vector_dimension = 300
        index = self.db._get_index()
        self.assertEqual(index, "test_collection_300")

if __name__ == '__main__':
    unittest.main()