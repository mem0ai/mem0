import os
import unittest

from embedchain.config import ElasticsearchDBConfig
from embedchain.vectordb.elasticsearch import ElasticsearchDB


class TestEsDB(unittest.TestCase):
    def setUp(self):
        self.es_config = ElasticsearchDBConfig(es_url="http://mock-url.net")
        self.vector_dim = 384

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
