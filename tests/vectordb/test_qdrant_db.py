import unittest
from unittest.mock import Mock

from embedchain.config import QdrantDBConfig
from embedchain.vectordb.qdrant_db import QdrantDB


class TestQrantDB(unittest.TestCase):
    def setUp(self):
        self.qdrant_config = QdrantDBConfig()
        self.vector_dim = 384

    def test_init_with_invalid_embedding_fn(self):
        # Test if an exception is raised when an invalid embedding_fn is provided
        with self.assertRaises(ValueError):
            QdrantDB(embedding_fn=None)

    def test_init_with_invalid_es_config(self):
        # Test if an exception is raised when an invalid config is provided
        with self.assertRaises(ValueError):
            QdrantDB(embedding_fn=Mock(), qdrant_config=None)

    def test_init_with_invalid_vector_dim(self):
        # Test if an exception is raised when an invalid vector_dim is provided
        with self.assertRaises(ValueError):
            QdrantDB(embedding_fn=Mock(), qdrant_config=self.qdrant_config, vector_dim=None)

    def test_init_with_invalid_collection_name(self):
        # Test if an exception is raised when an invalid collection_name is provided
        with self.assertRaises(ValueError):
            QdrantDB(
                embedding_fn=Mock(), qdrant_config=self.qdrant_config, vector_dim=self.vector_dim, collection_name=None
            )
