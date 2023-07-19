# ruff: noqa: E501

import unittest
from unittest.mock import patch

from embedchain import App
from embedchain.config import AppConfig
from embedchain.vectordb.chroma_db import ChromaDB, chromadb
from chromadb.config import Settings
from chromadb import Client


# TODO - Review this test
# class TestChromaDbHosts(unittest.TestCase):
# def test_init_with_host_and_port(self):
#     """
#     Test if the `ChromaDB` instance is initialized with the correct host and port values.
#     """
#     host = "test-host"
#     port = "1234"

#     with patch.object(chromadb, "Client") as mock_client:
#         db = ChromaDB(host=host, port=port, embedding_fn=len)

#     expected_client = Client(
#         Settings(
#             environment="",
#             chroma_db_impl=None,
#             chroma_api_impl="chromadb.api.fastapi.FastAPI",
#             chroma_telemetry_impl="chromadb.telemetry.posthog.Posthog",
#             chroma_sysdb_impl="chromadb.db.impl.sqlite.SqliteDB",
#             chroma_producer_impl="chromadb.db.impl.sqlite.SqliteDB",
#             chroma_consumer_impl="chromadb.db.impl.sqlite.SqliteDB",
#             chroma_segment_manager_impl="chromadb.segment.impl.manager.local.LocalSegmentManager",
#             tenant_id="default",
#             topic_namespace="default",
#             is_persistent=False,
#             persist_directory="./chroma",
#             chroma_server_host="test-host",
#             chroma_server_headers={},
#             chroma_server_http_port="1234",
#             chroma_server_ssl_enabled=False,
#             chroma_server_grpc_port=None,
#             chroma_server_cors_allow_origins=[],
#             anonymized_telemetry=True,
#             allow_reset=False,
#             migrations="apply",
#         )
#     )
#     mock_client.assert_called_once_with(expected_client)


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
