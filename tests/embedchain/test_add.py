import os
import unittest
from unittest.mock import MagicMock, patch

from embedchain import App


class TestApp(unittest.TestCase):
    os.environ["OPENAI_API_KEY"] = "test_key"

    def setUp(self):
        self.app = App()

    @patch("chromadb.api.models.Collection.Collection.add", MagicMock)
    def test_add(self):
        """
        Assumptions:
        The test calls the add method on an instance of App, passing in the strings "web_page" and "https://example.com".
        Asserts that the user_asks attribute of the App instance is equal to the nested list [["web_page", "https://example.com"]].
        """
        self.app.add("web_page", "https://example.com")
        self.assertEqual(self.app.user_asks, [["web_page", "https://example.com"]])
