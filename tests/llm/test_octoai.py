import os
import unittest
from unittest.mock import patch, MagicMock

from embedchain.config import BaseLlmConfig

from langchain.llms.octoai_endpoint import OctoAIEndpoint

class TestOctoaiLlm(unittest.TestCase):
    def setUp(self):
        os.environ["OCTOAI_API_KEY"] = "test_api_key"
        self.config = BaseLlmConfig(model="llama-2-7b-chat", max_new_tokens= 200, temperature=0.75, top_p=0.95)
        
    def test_init_raises_value_error_without_api_key(self):
        os.environ.pop("OCTOAI_API_TAKEN")
        with self.assertRaises(ValueError):
            OctoaiLlm()
            
    def test_init_raises_value_error_without_endpoint_url(self):
        os.environ.pop("ENDPOINT_URL")
        with self.assertRaises(ValueError):
            OctoaiLlm()
            
    
    @patch.dict(os.environ, {"OCTOAI_API_TOKEN": "octoai_api_token", "ENDPOINT_URL": "octoai_endpoint_url"})
    def test_get_llm_model_answer(self):
        # Test the get_llm_model_answer method
        llm = OctoaiLlm()
        prompt = "This is a test prompt."
        result = llm.get_llm_model_answer(prompt)
        self.assertIsInstance(result, str)
            