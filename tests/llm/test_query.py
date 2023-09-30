import os
import unittest
from unittest.mock import MagicMock, patch

from embedchain import App
from embedchain.config import AppConfig, BaseLlmConfig


class TestApp(unittest.TestCase):
    os.environ["OPENAI_API_KEY"] = "test_key"

    def setUp(self):
        self.app = App(config=AppConfig(collect_metrics=False))

    @patch("chromadb.api.models.Collection.Collection.add", MagicMock)
    def test_query(self):
        """
        This test checks the functionality of the 'query' method in the App class.
        It simulates a scenario where the 'retrieve_from_database' method returns a context list and
        'get_llm_model_answer' returns an expected answer string.

        The 'query' method is expected to call 'retrieve_from_database' and 'get_llm_model_answer' methods
        appropriately and return the right answer.

        Key assumptions tested:
        - 'retrieve_from_database' method is called exactly once with arguments: "Test query" and an instance of
            LlmConfig.
        - 'get_llm_model_answer' is called exactly once. The specific arguments are not checked in this test.
        - 'query' method returns the value it received from 'get_llm_model_answer'.

        The test isolates the 'query' method behavior by mocking out 'retrieve_from_database' and
        'get_llm_model_answer' methods.
        """
        with patch.object(self.app, "retrieve_from_database") as mock_retrieve:
            mock_retrieve.return_value = ["Test context"]
            with patch.object(self.app.llm, "get_llm_model_answer") as mock_answer:
                mock_answer.return_value = "Test answer"
                _answer = self.app.query(input_query="Test query")

        # Ensure retrieve_from_database was called
        mock_retrieve.assert_called_once()

        # Check the call arguments
        args, kwargs = mock_retrieve.call_args
        input_query_arg = kwargs.get("input_query")
        self.assertEqual(input_query_arg, "Test query")
        mock_answer.assert_called_once()

    @patch("embedchain.llm.openai.OpenAILlm._get_answer")
    def test_query_config_app_passing(self, mock_get_answer):
        mock_get_answer.return_value = MagicMock()
        mock_get_answer.return_value.content = "Test answer"

        config = AppConfig(collect_metrics=False)
        chat_config = BaseLlmConfig(system_prompt="Test system prompt")
        app = App(config=config, llm_config=chat_config)
        answer = app.llm.get_llm_model_answer("Test query")

        self.assertEqual(app.llm.config.system_prompt, "Test system prompt")
        self.assertEqual(answer, "Test answer")

    @patch("embedchain.llm.openai.OpenAILlm._get_answer")
    def test_app_passing(self, mock_get_answer):
        mock_get_answer.return_value = MagicMock()
        mock_get_answer.return_value.content = "Test answer"
        config = AppConfig(collect_metrics=False)
        chat_config = BaseLlmConfig()
        app = App(config=config, llm_config=chat_config, system_prompt="Test system prompt")
        answer = app.llm.get_llm_model_answer("Test query")
        self.assertEqual(app.llm.config.system_prompt, "Test system prompt")
        self.assertEqual(answer, "Test answer")

    @patch("chromadb.api.models.Collection.Collection.add", MagicMock)
    def test_query_with_where_in_params(self):
        """
        This test checks the functionality of the 'query' method in the App class.
        It simulates a scenario where the 'retrieve_from_database' method returns a context list based on
        a where filter and 'get_llm_model_answer' returns an expected answer string.

        The 'query' method is expected to call 'retrieve_from_database' with the where filter  and
        'get_llm_model_answer' methods appropriately and return the right answer.

        Key assumptions tested:
        - 'retrieve_from_database' method is called exactly once with arguments: "Test query" and an instance of
            LlmConfig.
        - 'get_llm_model_answer' is called exactly once. The specific arguments are not checked in this test.
        - 'query' method returns the value it received from 'get_llm_model_answer'.

        The test isolates the 'query' method behavior by mocking out 'retrieve_from_database' and
        'get_llm_model_answer' methods.
        """
        with patch.object(self.app, "retrieve_from_database") as mock_retrieve:
            mock_retrieve.return_value = ["Test context"]
            with patch.object(self.app.llm, "get_llm_model_answer") as mock_answer:
                mock_answer.return_value = "Test answer"
                answer = self.app.query("Test query", where={"attribute": "value"})

        self.assertEqual(answer, "Test answer")
        _args, kwargs = mock_retrieve.call_args
        self.assertEqual(kwargs.get("input_query"), "Test query")
        self.assertEqual(kwargs.get("where"), {"attribute": "value"})
        mock_answer.assert_called_once()

    @patch("chromadb.api.models.Collection.Collection.add", MagicMock)
    def test_query_with_where_in_query_config(self):
        """
        This test checks the functionality of the 'query' method in the App class.
        It simulates a scenario where the 'retrieve_from_database' method returns a context list based on
        a where filter and 'get_llm_model_answer' returns an expected answer string.

        The 'query' method is expected to call 'retrieve_from_database' with the where filter  and
        'get_llm_model_answer' methods appropriately and return the right answer.

        Key assumptions tested:
        - 'retrieve_from_database' method is called exactly once with arguments: "Test query" and an instance of
            LlmConfig.
        - 'get_llm_model_answer' is called exactly once. The specific arguments are not checked in this test.
        - 'query' method returns the value it received from 'get_llm_model_answer'.

        The test isolates the 'query' method behavior by mocking out 'retrieve_from_database' and
        'get_llm_model_answer' methods.
        """

        with patch.object(self.app.llm, "get_llm_model_answer") as mock_answer:
            mock_answer.return_value = "Test answer"
            with patch.object(self.app.db, "query") as mock_database_query:
                mock_database_query.return_value = ["Test context"]
                llm_config = BaseLlmConfig(where={"attribute": "value"})
                answer = self.app.query("Test query", llm_config)

        self.assertEqual(answer, "Test answer")
        _args, kwargs = mock_database_query.call_args
        self.assertEqual(kwargs.get("input_query"), "Test query")
        self.assertEqual(kwargs.get("where"), {"attribute": "value"})
        mock_answer.assert_called_once()
