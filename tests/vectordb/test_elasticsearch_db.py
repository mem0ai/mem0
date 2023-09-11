import unittest

from embedchain.config import ElasticsearchDBConfig
from embedchain.embedder.base import BaseEmbedder
from embedchain.vectordb.elasticsearch import ElasticsearchDB


class TestEsDB(unittest.TestCase):
    def setUp(self):
        self.es_config = ElasticsearchDBConfig()
        self.vector_dim = 384

    def test_init_with_invalid_es_config(self):
        # Test if an exception is raised when an invalid es_config is provided
        with self.assertRaises(ValueError):
            ElasticsearchDB(es_config=None)

    def test_init_with_invalid_vector_dim(self):
        # Test if an exception is raised when an invalid vector_dim is provided
        embedder = BaseEmbedder()
        embedder.set_vector_dimension(None)
        with self.assertRaises(ValueError):
            ElasticsearchDB(es_config=self.es_config)

    def test_init_with_invalid_collection_name(self):
        # Test if an exception is raised when an invalid collection_name is provided
        self.es_config.collection_name = None
        with self.assertRaises(ValueError):
            ElasticsearchDB(es_config=self.es_config)
