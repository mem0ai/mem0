import unittest
from unittest.mock import Mock

from embedchain.config import ElasticsearchDBConfig
from embedchain.vectordb.elasticsearch_db import ElasticsearchDB


class TestEsDB(unittest.TestCase):
    def setUp(self):
        self.es_config = ElasticsearchDBConfig()
        self.vector_dim = 384

    def test_init_with_invalid_embedding_fn(self):
        # Test if an exception is raised when an invalid embedding_fn is provided
        with self.assertRaises(ValueError):
            ElasticsearchDB(embedding_fn=None)

    def test_init_with_invalid_es_config(self):
        # Test if an exception is raised when an invalid es_config is provided
        with self.assertRaises(ValueError):
            ElasticsearchDB(embedding_fn=Mock(), es_config=None)

    def test_init_with_invalid_vector_dim(self):
        # Test if an exception is raised when an invalid vector_dim is provided
        with self.assertRaises(ValueError):
            ElasticsearchDB(embedding_fn=Mock(), es_config=self.es_config, vector_dim=None)

    def test_init_with_invalid_collection_name(self):
        # Test if an exception is raised when an invalid collection_name is provided
        with self.assertRaises(ValueError):
            ElasticsearchDB(
                embedding_fn=Mock(), es_config=self.es_config, vector_dim=self.vector_dim, collection_name=None
            )
