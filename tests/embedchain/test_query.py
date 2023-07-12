import os
import unittest
from unittest.mock import MagicMock, patch

from embedchain import App
from embedchain.embedchain import QueryConfig


class TestApp(unittest.TestCase):
    os.environ["OPENAI_API_KEY"] = "test_key"

    def setUp(self):
        self.app = App()

    @patch("chromadb.api.models.Collection.Collection.add", MagicMock)
    def test_query(self):
        """
        Assumptions:
        Calls retrieve_from_database exactly once with "Test query" and an instance of QueryConfig as arguments.
        Calls get_llm_model_answer exactly once. You're not checking the arguments in this case.
        Returns the value it received from get_llm_model_answer.
        """
        with patch.object(self.app, "retrieve_from_database") as mock_retrieve:
            mock_retrieve.return_value = ["Test context"]
            with patch.object(self.app, "get_llm_model_answer") as mock_answer:
                mock_answer.return_value = "Test answer"
                answer = self.app.query("Test query")

        self.assertEqual(answer, "Test answer")
        self.assertEqual(mock_retrieve.call_args[0][0], "Test query")
        self.assertIsInstance(mock_retrieve.call_args[0][1], QueryConfig)
        mock_answer.assert_called_once()
