import os
import unittest
from string import Template
from unittest.mock import patch

from embedchain import App
from embedchain.embedchain import QueryConfig


class TestApp(unittest.TestCase):
    os.environ["OPENAI_API_KEY"] = "test_key"

    def setUp(self):
        self.app = App()

    @patch("logging.info")
    def test_query_logs_same_prompt_as_dry_run(self, mock_logging_info):
        """
        Test that the 'query' method logs the same prompt as the 'dry_run' method.
        This is the only way I found to test the prompt in query, that's not returned.
        """
        with patch.object(self.app, "retrieve_from_database") as mock_retrieve:
            mock_retrieve.return_value = ["Test context"]
            input_query = "Test query"
            config = QueryConfig(
                number_documents=3,
                template=Template("Question: $query, context: $context, history: $history"),
                history=["Past context 1", "Past context 2"],
            )

            with patch.object(self.app, "get_answer_from_llm"):
                self.app.dry_run(input_query, config)
                self.app.query(input_query, config)

            # Access the log messages captured during the execution
            logged_messages = [call[0][0] for call in mock_logging_info.call_args_list]

            # Extract the prompts from the log messages
            dry_run_prompt = self.extract_prompt(logged_messages[0])
            query_prompt = self.extract_prompt(logged_messages[1])

            # Perform assertions on the prompts
            self.assertEqual(dry_run_prompt, query_prompt)

    def extract_prompt(self, log_message):
        """
        Extracts the prompt value from the log message.
        Adjust this method based on the log message format in your implementation.
        """
        # Modify this logic based on your log message format
        prefix = "Prompt: "
        return log_message.split(prefix, 1)[1]
