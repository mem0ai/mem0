import os
import unittest
from unittest.mock import patch

from embedchain.config import BaseLlmConfig
from embedchain.llm.cohere import CohereLlm


class TestCohereLlm(unittest.TestCase):
    def setUp(self):
        os.environ["COHERE_API_KEY"] = "test_api_key"
        self.config = BaseLlmConfig(model="gptd-instruct-tft", max_tokens=50, temperature=0.7, top_p=0.8)

    def test_init_raises_value_error_without_api_key(self):
        os.environ.pop("COHERE_API_KEY")
        with self.assertRaises(ValueError):
            CohereLlm()

    def test_get_llm_model_answer_raises_value_error_for_system_prompt(self):
        llm = CohereLlm(self.config)
        llm.config.system_prompt = "system_prompt"
        with self.assertRaises(ValueError):
            llm.get_llm_model_answer("prompt")

    @patch("embedchain.llm.cohere.CohereLlm._get_answer")
    def test_get_llm_model_answer(self, mock_get_answer):
        mock_get_answer.return_value = "Test answer"

        llm = CohereLlm(self.config)
        answer = llm.get_llm_model_answer("Test query")

        self.assertEqual(answer, "Test answer")
        mock_get_answer.assert_called_once()
