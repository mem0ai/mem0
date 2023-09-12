import unittest
import os

from embedchain.config import ElasticsearchDBConfig
from embedchain.vectordb.elasticsearch import ElasticsearchDB


class TestEsDB(unittest.TestCase):
    def setUp(self):
        self.es_config = ElasticsearchDBConfig()
        self.vector_dim = 384

    def test_init_without_url(self):
        del os.environ["ELASTICSEARCH_URL"]
        # Test if an exception is raised when an invalid es_config is provided
        with self.assertRaises(AttributeError):
            ElasticsearchDB()

    def test_init_with_invalid_es_config(self):
        # Test if an exception is raised when an invalid es_config is provided
        with self.assertRaises(ValueError):
            ElasticsearchDB(es_config={"valid es_config": False})

    def test_init_with_invalid_collection_name(self):
        # Test if an exception is raised when an invalid collection_name is provided
        self.es_config.collection_name = None
        with self.assertRaises(ValueError):
            ElasticsearchDB(es_config=self.es_config)
