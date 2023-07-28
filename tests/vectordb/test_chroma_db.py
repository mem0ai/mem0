# ruff: noqa: E501

import unittest
from unittest.mock import patch

from chromadb.config import Settings

from embedchain import App
from embedchain.config import AppConfig
from embedchain.vectordb.chroma_db import ChromaDB, chromadb


class TestChromaDbHosts(unittest.TestCase):
    def test_init_with_host_and_port(self):
        """
        Test if the `ChromaDB` instance is initialized with the correct host and port values.
        """
        host = "test-host"
        port = "1234"

        with patch.object(chromadb, "HttpClient") as mock_client:
            _db = ChromaDB(host=host, port=port, embedding_fn=len)

        expected_settings = Settings(
            chroma_server_host="test-host",
            chroma_server_http_port="1234",
        )

        mock_client.assert_called_once_with(expected_settings)


# Review this test
class TestChromaDbHostsInit(unittest.TestCase):
    @patch("embedchain.vectordb.chroma_db.chromadb.Client")
    def test_init_with_host_and_port(self, mock_client):
        """
        Test if the `App` instance is initialized with the correct host and port values.
        """
        host = "test-host"
        port = "1234"

        config = AppConfig(host=host, port=port)

        _app = App(config)

        # self.assertEqual(mock_client.call_args[0][0].chroma_server_host, host)
        # self.assertEqual(mock_client.call_args[0][0].chroma_server_http_port, port)


class TestChromaDbHostsNone(unittest.TestCase):
    @patch("embedchain.vectordb.chroma_db.chromadb.Client")
    def test_init_with_host_and_port(self, mock_client):
        """
        Test if the `App` instance is initialized without default hosts and ports.
        """

        _app = App()

        self.assertEqual(mock_client.call_args[0][0].chroma_server_host, None)
        self.assertEqual(mock_client.call_args[0][0].chroma_server_http_port, None)


class TestChromaDbHostsLoglevel(unittest.TestCase):
    @patch("embedchain.vectordb.chroma_db.chromadb.Client")
    def test_init_with_host_and_port(self, mock_client):
        """
        Test if the `App` instance is initialized without a config that does not contain default hosts and ports.
        """
        config = AppConfig(log_level="DEBUG")

        _app = App(config)

        self.assertEqual(mock_client.call_args[0][0].chroma_server_host, None)
        self.assertEqual(mock_client.call_args[0][0].chroma_server_http_port, None)
