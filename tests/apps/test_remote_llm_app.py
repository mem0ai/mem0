# ruff: noqa: E501
# Test with the command: python -m unittest tests/apps/test_remote_llm_app.py
import os
import unittest
from unittest.mock import patch, MagicMock

from embedchain import RemoteLLMApp
from embedchain.config import RemoteLLMConfig

class TestRemoteLLMApp(unittest.TestCase):

    def setUp(self) -> None:
        config = RemoteLLMConfig(endpoint_url="http://fakeurl.com/generate", response_key="generated_texts")
        self.app = RemoteLLMApp(config=config)

    @patch('requests.post')
    def test_inference_success(self, mock_post):
        # Create a mock response with status_code 200 and a JSON payload
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"generated_texts": "Hello world!"}
        mock_post.return_value = mock_response

        prompt = "Hello"
        result = self.app.get_llm_model_answer(prompt)
        self.assertEqual(result, "Hello world!")

    @patch('requests.post')
    def test_inferece_failure(self, mock_get):
        # Create a mock response with status_code 404
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        prompt = "Hello"
        with self.assertRaises(Exception):
            self.app.get_llm_model_answer(prompt)

        # Create a mock response without the response key.
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_get.return_value = mock_response

        prompt = "Hello"
        with self.assertRaises(ValueError):
            self.app.get_llm_model_answer(prompt)

            

