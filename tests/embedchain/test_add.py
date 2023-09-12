import os
import unittest
from unittest.mock import MagicMock, patch

from embedchain import App
from embedchain.config import AddConfig, AppConfig, ChunkerConfig
from embedchain.models.data_type import DataType


class TestApp(unittest.TestCase):
    os.environ["OPENAI_API_KEY"] = "test_key"

    def setUp(self):
        self.app = App(config=AppConfig(collect_metrics=False))

    @patch("chromadb.api.models.Collection.Collection.add", MagicMock)
    def test_add(self):
        """
        This test checks the functionality of the 'add' method in the App class.
        It begins by simulating the addition of a web page with a specific URL to the application instance.
        The 'add' method is expected to append the input type and URL to the 'user_asks' attribute of the App instance.
        By asserting that 'user_asks' is updated correctly after the 'add' method is called, we can confirm that the
        method is working as intended.
        The Collection.add method from the chromadb library is mocked during this test to isolate the behavior of the
        'add' method.
        """
        self.app.add("https://example.com", metadata={"meta": "meta-data"})
        self.assertEqual(self.app.user_asks, [["https://example.com", "web_page", {"meta": "meta-data"}]])

    @patch("chromadb.api.models.Collection.Collection.add", MagicMock)
    def test_add_forced_type(self):
        """
        Test that you can also force a data_type with `add`.
        """
        data_type = "text"
        self.app.add("https://example.com", data_type=data_type, metadata={"meta": "meta-data"})
        self.assertEqual(self.app.user_asks, [["https://example.com", data_type, {"meta": "meta-data"}]])

    @patch("chromadb.api.models.Collection.Collection.add", MagicMock)
    def test_dry_run(self):
        """
        Test that if dry_run == True then data chunks are returned.
        """

        chunker_config = ChunkerConfig(chunk_size=1, chunk_overlap=0)
        # We can't test with lorem ipsum because chunks are deduped, so would be recurring characters.
        text = """0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"""

        result = self.app.add(source=text, config=AddConfig(chunker=chunker_config), dry_run=True)

        chunks = result["chunks"]
        metadata = result["metadata"]
        count = result["count"]
        data_type = result["type"]

        self.assertEqual(len(chunks), len(text))
        self.assertEqual(count, len(text))
        self.assertEqual(data_type, DataType.TEXT)
        for item in metadata:
            self.assertIsInstance(item, dict)
            self.assertIn(item["url"], "local")
            self.assertIn(item["data_type"], "text")
