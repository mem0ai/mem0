import os
import unittest
from unittest.mock import MagicMock, patch

from embedchain import App
from embedchain.config import AppConfig, BaseLlmConfig
from embedchain.llm.base import BaseLlm
from embedchain.memory.base import ChatHistory
from embedchain.memory.message import ChatMessage


class TestApp(unittest.TestCase):
    def setUp(self):
        os.environ["OPENAI_API_KEY"] = "test_key"
        self.app = App(config=AppConfig(collect_metrics=False))

    @patch.object(App, "_retrieve_from_database", return_value=["Test context"])
    @patch.object(BaseLlm, "get_answer_from_llm", return_value="Test answer")
    def test_chat_with_memory(self, mock_get_answer, mock_retrieve):
        """
        This test checks the functionality of the 'chat' method in the App class with respect to the chat history
        memory.
        The 'chat' method is called twice. The first call initializes the chat history memory.
        The second call is expected to use the chat history from the first call.

        Key assumptions tested:
            called with correct arguments, adding the correct chat history.
        - After the first call, 'memory.chat_memory.add_user_message' and 'memory.chat_memory.add_ai_message' are
        - During the second call, the 'chat' method uses the chat history from the first call.

        The test isolates the 'chat' method behavior by mocking out '_retrieve_from_database', 'get_answer_from_llm' and
        'memory' methods.
        """
        config = AppConfig(collect_metrics=False)
        app = App(config=config)
        with patch.object(BaseLlm, "add_history") as mock_history:
            first_answer = app.chat("Test query 1")
            self.assertEqual(first_answer, "Test answer")
            mock_history.assert_called_with(app.config.id, "Test query 1", "Test answer", session_id="default")

            second_answer = app.chat("Test query 2", session_id="test_session")
            self.assertEqual(second_answer, "Test answer")
            mock_history.assert_called_with(app.config.id, "Test query 2", "Test answer", session_id="test_session")

    @patch.object(App, "_retrieve_from_database", return_value=["Test context"])
    @patch.object(BaseLlm, "get_answer_from_llm", return_value="Test answer")
    def test_template_replacement(self, mock_get_answer, mock_retrieve):
        """
        Tests that if a default template is used and it doesn't contain history,
        the default template is swapped in.

        Also tests that a dry run does not change the history
        """
        with patch.object(ChatHistory, "get") as mock_memory:
            mock_message = ChatMessage()
            mock_message.add_user_message("Test query 1")
            mock_message.add_ai_message("Test answer")
            mock_memory.return_value = [mock_message]

            config = AppConfig(collect_metrics=False)
            app = App(config=config)
            first_answer = app.chat("Test query 1")
            self.assertEqual(first_answer, "Test answer")
            self.assertEqual(len(app.llm.history), 1)
            history = app.llm.history
            dry_run = app.chat("Test query 2", dry_run=True)
            self.assertIn("Conversation history:", dry_run)
            self.assertEqual(history, app.llm.history)
            self.assertEqual(len(app.llm.history), 1)

    @patch("chromadb.api.models.Collection.Collection.add", MagicMock)
    def test_chat_with_where_in_params(self):
        """
        Test where filter
        """
        with patch.object(self.app, "_retrieve_from_database") as mock_retrieve:
            mock_retrieve.return_value = ["Test context"]
            with patch.object(self.app.llm, "get_llm_model_answer") as mock_answer:
                mock_answer.return_value = "Test answer"
                answer = self.app.chat("Test query", where={"attribute": "value"})

        self.assertEqual(answer, "Test answer")
        _args, kwargs = mock_retrieve.call_args
        self.assertEqual(kwargs.get("input_query"), "Test query")
        self.assertEqual(kwargs.get("where"), {"attribute": "value"})
        mock_answer.assert_called_once()

    @patch("chromadb.api.models.Collection.Collection.add", MagicMock)
    def test_chat_with_where_in_chat_config(self):
        """
        This test checks the functionality of the 'chat' method in the App class.
        It simulates a scenario where the '_retrieve_from_database' method returns a context list based on
        a where filter and 'get_llm_model_answer' returns an expected answer string.

        The 'chat' method is expected to call '_retrieve_from_database' with the where filter specified
        in the BaseLlmConfig and 'get_llm_model_answer' methods appropriately and return the right answer.

        Key assumptions tested:
        - '_retrieve_from_database' method is called exactly once with arguments: "Test query" and an instance of
            BaseLlmConfig.
        - 'get_llm_model_answer' is called exactly once. The specific arguments are not checked in this test.
        - 'chat' method returns the value it received from 'get_llm_model_answer'.

        The test isolates the 'chat' method behavior by mocking out '_retrieve_from_database' and
        'get_llm_model_answer' methods.
        """
        with patch.object(self.app.llm, "get_llm_model_answer") as mock_answer:
            mock_answer.return_value = "Test answer"
            with patch.object(self.app.db, "query") as mock_database_query:
                mock_database_query.return_value = ["Test context"]
                llm_config = BaseLlmConfig(where={"attribute": "value"})
                answer = self.app.chat("Test query", llm_config)

        self.assertEqual(answer, "Test answer")
        _args, kwargs = mock_database_query.call_args
        self.assertEqual(kwargs.get("input_query"), "Test query")
        where = kwargs.get("where")
        assert "app_id" in where
        assert "attribute" in where
        mock_answer.assert_called_once()
