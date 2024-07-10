import os
import unittest
from unittest.mock import patch

from embedchain import App
from embedchain.config import AppConfig, ElasticsearchDBConfig
from embedchain.embedder.gpt4all import GPT4AllEmbedder
from embedchain.vectordb.elasticsearch import ElasticsearchDB


class TestEsDB(unittest.TestCase):
    @patch("embedchain.vectordb.elasticsearch.Elasticsearch")
    def test_setUp(self, mock_client):
        self.db = ElasticsearchDB(config=ElasticsearchDBConfig(es_url="https://localhost:9200"))
        self.vector_dim = 384
        app_config = AppConfig(collect_metrics=False)
        self.app = App(config=app_config, db=self.db)

        # Assert that the Elasticsearch client is stored in the ElasticsearchDB class.
        self.assertEqual(self.db.client, mock_client.return_value)

    @patch("embedchain.vectordb.elasticsearch.Elasticsearch")
    def test_query(self, mock_client):
        self.db = ElasticsearchDB(config=ElasticsearchDBConfig(es_url="https://localhost:9200"))
        app_config = AppConfig(collect_metrics=False)
        self.app = App(config=app_config, db=self.db, embedding_model=GPT4AllEmbedder())

        # Assert that the Elasticsearch client is stored in the ElasticsearchDB class.
        self.assertEqual(self.db.client, mock_client.return_value)

        # Create some dummy data
        documents = ["This is a document.", "This is another document."]
        metadatas = [{"url": "url_1", "doc_id": "doc_id_1"}, {"url": "url_2", "doc_id": "doc_id_2"}]
        ids = ["doc_1", "doc_2"]

        # Add the data to the database.
        self.db.add(documents, metadatas, ids)

        search_response = {
            "hits": {
                "hits": [
                    {
                        "_source": {"text": "This is a document.", "metadata": {"url": "url_1", "doc_id": "doc_id_1"}},
                        "_score": 0.9,
                    },
                    {
                        "_source": {
                            "text": "This is another document.",
                            "metadata": {"url": "url_2", "doc_id": "doc_id_2"},
                        },
                        "_score": 0.8,
                    },
                ]
            }
        }

        # Configure the mock client to return the mocked response.
        mock_client.return_value.search.return_value = search_response

        # Query the database for the documents that are most similar to the query "This is a document".
        query = "This is a document"
        results_without_citations = self.db.query(query, n_results=2, where={})
        expected_results_without_citations = ["This is a document.", "This is another document."]
        self.assertEqual(results_without_citations, expected_results_without_citations)

        results_with_citations = self.db.query(query, n_results=2, where={}, citations=True)
        expected_results_with_citations = [
            ("This is a document.", {"url": "url_1", "doc_id": "doc_id_1", "score": 0.9}),
            ("This is another document.", {"url": "url_2", "doc_id": "doc_id_2", "score": 0.8}),
        ]
        self.assertEqual(results_with_citations, expected_results_with_citations)

    def test_init_without_url(self):
        # Make sure it's not loaded from env
        try:
            del os.environ["ELASTICSEARCH_URL"]
        except KeyError:
            pass
        # Test if an exception is raised when an invalid es_config is provided
        with self.assertRaises(AttributeError):
            ElasticsearchDB()

    def test_init_with_invalid_es_config(self):
        # Test if an exception is raised when an invalid es_config is provided
        with self.assertRaises(TypeError):
            ElasticsearchDB(es_config={"ES_URL": "some_url", "valid es_config": False})
