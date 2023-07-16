import os
import unittest
from unittest.mock import patch

from embedchain import App


class TestApp(unittest.TestCase):
    os.environ["OPENAI_API_KEY"] = "test_key"

    def setUp(self):
        self.app = App()

    @patch("embedchain.embedchain.memory", autospec=True)
    @patch.object(App, "retrieve_from_database", return_value=["Test context"])
    @patch.object(App, "get_answer_from_llm", return_value="Test answer")
    def test_chat_with_memory(self, mock_answer, mock_retrieve, mock_memory):
        """
        This test checks the functionality of the 'chat' method in the App class with respect to the chat history
        memory.
        The 'chat' method is called twice. The first call initializes the chat history memory.
        The second call is expected to use the chat history from the first call.

        Key assumptions tested:
        - After the first call, 'memory.chat_memory.add_user_message' and 'memory.chat_memory.add_ai_message' are
            called with correct arguments, adding the correct chat history.
        - During the second call, the 'chat' method uses the chat history from the first call.

        The test isolates the 'chat' method behavior by mocking out 'retrieve_from_database', 'get_answer_from_llm' and
        'memory' methods.
        """
        mock_memory.load_memory_variables.return_value = {"history": []}
        app = App()

        # First call to chat
        first_answer = app.chat("Test query 1")
        self.assertEqual(first_answer, "Test answer")
        mock_memory.chat_memory.add_user_message.assert_called_once_with("Test query 1")
        mock_memory.chat_memory.add_ai_message.assert_called_once_with("Test answer")

        mock_memory.chat_memory.add_user_message.reset_mock()
        mock_memory.chat_memory.add_ai_message.reset_mock()

        # Second call to chat
        second_answer = app.chat("Test query 2")
        self.assertEqual(second_answer, "Test answer")
        mock_memory.chat_memory.add_user_message.assert_called_once_with("Test query 2")
        mock_memory.chat_memory.add_ai_message.assert_called_once_with("Test answer")
