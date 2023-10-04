import importlib
import os
import unittest
from unittest.mock import patch

from embedchain.config import BaseLlmConfig
from embedchain.llm.hugging_face_hub import HuggingFaceHubLlm


class TestHuggingFaceHubLlm(unittest.TestCase):
    def setUp(self):
        os.environ["HUGGINGFACEHUB_API_TOKEN"] = "test_api_key"
        self.config = BaseLlmConfig(model="google/flan-t5-xxl", max_tokens=50, temperature=0.7, top_p=0.8)

    def test_init_raises_value_error_without_api_key(self):
        os.environ.pop("HUGGINGFACEHUB_API_TOKEN")
        with self.assertRaises(ValueError):
            HuggingFaceHubLlm()

    def test_get_llm_model_answer_raises_value_error_for_system_prompt(self):
        llm = HuggingFaceHubLlm(self.config)
        llm.config.system_prompt = "system_prompt"
        with self.assertRaises(ValueError):
            llm.get_llm_model_answer("prompt")

    def test_top_p_value_within_range(self):
        config = BaseLlmConfig(top_p=1.0)
        with self.assertRaises(ValueError):
            HuggingFaceHubLlm._get_answer("test_prompt", config)

    def test_importlib_is_imported(self):
        importlib_installed = True
        try:
            importlib.import_module("huggingface_hub")
        except ImportError:
            importlib_installed = False
        self.assertTrue(importlib_installed)

    @patch("embedchain.llm.hugging_face_hub.HuggingFaceHubLlm._get_answer")
    def test_get_llm_model_answer(self, mock_get_answer):
        mock_get_answer.return_value = "Test answer"

        llm = HuggingFaceHubLlm(self.config)
        answer = llm.get_llm_model_answer("Test query")

        self.assertEqual(answer, "Test answer")
        mock_get_answer.assert_called_once()
