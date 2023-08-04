import unittest
from unittest.mock import MagicMock, Mock, patch

from embedchain.vectordb.elasticsearch_db import EsDB


class TestEsDB(unittest.TestCase):
    def setUp(self):
        # set mock es client
        self.mock_client = MagicMock()
        self.mock_client.indices.exists.return_value = True

    def test_init_with_invalid_embedding_fn(self):
        # Test if an exception is raised when an invalid embedding_fn is provided
        with self.assertRaises(ValueError):
            EsDB(embedding_fn=None)

    def test_init_with_invalid_vector_dim(self):
        # Test if an exception is raised when an invalid vector_dim is provided
        with self.assertRaises(ValueError):
            EsDB(embedding_fn=Mock(), es_client=self.mock_client, vector_dim=None)

    def test_init_with_valid_embedding_and_client(self):
        # check for successful creation of EsDB instance
        esdb = EsDB(embedding_fn=Mock(), es_client=self.mock_client, vector_dim=1024)
        self.assertIsInstance(esdb, EsDB)

    @patch("os.getenv")  # Mock the os.getenv function to return None for ES_ENDPOINT
    def test_init_with_missing_endpoint(self, mock_os_getenv):
        # Test if an exception is raised when ES_ENDPOINT is missing
        mock_os_getenv.return_value = None
        with self.assertRaises(ValueError):
            EsDB(embedding_fn=Mock())
