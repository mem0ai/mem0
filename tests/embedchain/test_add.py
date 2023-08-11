import os
import unittest
from unittest.mock import MagicMock, patch

from embedchain import App
from embedchain.config import AppConfig


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
        self.app.add("web_page", "https://example.com", {"meta": "meta-data"})
        self.assertEqual(self.app.user_asks, [["web_page", "https://example.com", {"meta": "meta-data"}]])
