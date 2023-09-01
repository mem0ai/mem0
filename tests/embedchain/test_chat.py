import os
import unittest
from unittest.mock import patch

from embedchain import App
from embedchain.config import AppConfig


class TestApp(unittest.TestCase):
    def setUp(self):
        os.environ["OPENAI_API_KEY"] = "test_key"
        self.app = App(config=AppConfig(collect_metrics=False))

    @patch.object(App, "retrieve_from_database", return_value=["Test context"])
    @patch.object(App, "get_answer_from_llm", return_value="Test answer")
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

        The test isolates the 'chat' method behavior by mocking out 'retrieve_from_database', 'get_answer_from_llm' and
        'memory' methods.
        """
        app = App()
        first_answer = app.chat("Test query 1")
        self.assertEqual(first_answer, "Test answer")
        self.assertEqual(len(app.memory.chat_memory.messages), 2)
        second_answer = app.chat("Test query 2")
        self.assertEqual(second_answer, "Test answer")
        self.assertEqual(len(app.memory.chat_memory.messages), 4)
