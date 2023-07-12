import unittest
from unittest.mock import patch

from embedchain.vectordb.chroma_db import ChromaDB
from embedchain.vectordb.chroma_db import chromadb


class TestChromaDB(unittest.TestCase):
    def test_init_with_host_and_port(self):
        """
        Test if the `ChromaDB` instance is initialized with the correct host and port values.
        """
        host = "test-host"
        port = "1234"

        with patch.object(chromadb, "Client") as mock_client:
            db = ChromaDB(host=host, port=port)

        expected_settings = chromadb.config.Settings(
            chroma_api_impl="rest",
            chroma_server_host=host,
            chroma_server_http_port=port,
        )

        mock_client.assert_called_once_with(expected_settings)


if __name__ == "__main__":
    unittest.main()
