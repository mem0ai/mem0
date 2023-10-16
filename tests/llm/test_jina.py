import os
import unittest
from unittest.mock import patch

from embedchain.config import BaseLlmConfig
from embedchain.llm.jina import JinaLlm


class TestJinaLlm(unittest.TestCase):
    def setUp(self):
        os.environ["JINACHAT_API_KEY"] = "test_api_key"
        self.config = BaseLlmConfig(
            temperature=0.7, max_tokens=50, top_p=0.8, stream=False, system_prompt="System prompt"
        )

    def test_init_raises_value_error_without_api_key(self):
        os.environ.pop("JINACHAT_API_KEY")
        with self.assertRaises(ValueError):
            JinaLlm()

    @patch("embedchain.llm.jina.JinaLlm._get_answer")
    def test_get_llm_model_answer(self, mock_get_answer):
        mock_get_answer.return_value = "Test answer"

        llm = JinaLlm(self.config)
        answer = llm.get_llm_model_answer("Test query")

        self.assertEqual(answer, "Test answer")
        mock_get_answer.assert_called_once()

    @patch("embedchain.llm.jina.JinaLlm._get_answer")
    def test_get_llm_model_answer_with_system_prompt(self, mock_get_answer):
        self.config.system_prompt = "Custom system prompt"
        mock_get_answer.return_value = "Test answer"

        llm = JinaLlm(self.config)
        answer = llm.get_llm_model_answer("Test query")

        self.assertEqual(answer, "Test answer")
        mock_get_answer.assert_called_once()
