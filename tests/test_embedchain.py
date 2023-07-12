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
        self.app.add("web_page", "https://example.com")
        self.assertEqual(self.app.user_asks, [["web_page", "https://example.com"]])

    @patch("chromadb.api.models.Collection.Collection.add", MagicMock)
    def test_query(self):
        with patch.object(self.app, "retrieve_from_database") as mock_retrieve:
            mock_retrieve.return_value = "Test context"
            with patch.object(self.app, "get_llm_model_answer") as mock_answer:
                mock_answer.return_value = "Test answer"
                answer = self.app.query("Test query")

        self.assertEqual(answer, "Test answer")
        mock_retrieve.assert_called_once_with("Test query")
        mock_answer.assert_called_once()
