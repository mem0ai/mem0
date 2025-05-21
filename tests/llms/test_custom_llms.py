import unittest
from unittest.mock import patch, MagicMock
import json
import requests # For requests.exceptions.HTTPError

# LLM Classes to test
from mem0.llms.silicon_life import SiliconLifeLLM
from mem0.llms.deepseek import DeepseekLLM

# Config
from mem0.configs.llms.base import BaseLlmConfig

class TestSiliconLifeLLM(unittest.TestCase):
    def setUp(self):
        self.config = BaseLlmConfig(
            api_key="test_silicon_life_api_key",
            model="siliconlife-test-model",
            # ASIF: The implementation uses 'silicon_life_base_url' if available,
            # otherwise defaults. We should test with it being explicitly set.
            silicon_life_base_url="https://mock.api.siliconlife.ai/v1/chat/completions"
        )
        self.llm = SiliconLifeLLM(config=self.config)
        self.messages = [{"role": "user", "content": "Hello"}]

    @patch('requests.post')
    def test_generate_response_success(self, mock_post):
        # Configure mock response for success
        mock_response_data = {"choices": [{"message": {"content": "Test SiliconLife Response"}}]}
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.json.return_value = mock_response_data
        mock_post.return_value.raise_for_status = MagicMock()

        response = self.llm.generate_response(messages=self.messages)

        # Assertions
        expected_url = self.config.silicon_life_base_url
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], expected_url)
        self.assertEqual(kwargs['headers']['Authorization'], f"Bearer {self.config.api_key}")
        
        payload = json.loads(kwargs['data'])
        self.assertEqual(payload['model'], self.config.model)
        self.assertEqual(payload['messages'], self.messages)
        
        self.assertEqual(response, "Test SiliconLife Response")

    @patch('requests.post')
    def test_generate_response_api_error(self, mock_post):
        # Configure mock to raise HTTPError
        mock_post.return_value = MagicMock(status_code=500)
        mock_post.return_value.raise_for_status.side_effect = requests.exceptions.HTTPError("API Error")

        with self.assertRaises(ConnectionError) as context:
            self.llm.generate_response(messages=self.messages)
        
        self.assertTrue("Failed to connect to SiliconLifeLLM API" in str(context.exception))
        mock_post.assert_called_once()

    @patch('requests.post')
    def test_generate_response_with_tool_call_success(self, mock_post):
        mock_tool_call_data = {
            "id": "call_abc123",
            "function": {
                "name": "get_weather",
                "arguments": json.dumps({"location": "Paris"}) # Arguments are a JSON string
            },
            "type": "function"
        }
        # ASIF: The current SiliconLifeLLM implementation returns the whole response_data as JSON string
        # if it detects 'tools' were in the payload and the response isn't simple text.
        # Let's simulate a response that would trigger this.
        # The actual API might return tool_calls inside choices[0].message.
        # Given the implementation detail, we mock a response that might not be typical
        # but tests the current code path.
        # For a more robust test, we might need to assume a structure like OpenAI:
        # mock_response_data = {"choices": [{"message": {"tool_calls": [mock_tool_call_data]}}]}
        # However, the current implementation returns json.dumps(response_data) if tools were in payload.
        # Let's assume the API returns something that is not the simple 'content' structure.
        
        # Simulating a response that isn't just `{"choices": [{"message": {"content": "..."}}]}`
        # but rather something that would make it fall into the "return raw JSON" path
        # when tools are involved.
        # The current implementation returns json.dumps(response_data) when tools are requested
        # and the specific 'choices[0].message.content' path is not found.
        # This test is a bit tricky due to the placeholder nature of the LLM.
        # Let's assume the API returns the tool call directly in a way that bypasses simple content extraction.
        # A more realistic scenario for tool calls would be:
        mock_api_response = {"choices": [{"message": {"tool_calls": [mock_tool_call_data]}}]}

        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.json.return_value = mock_api_response
        mock_post.return_value.raise_for_status = MagicMock()

        tools = [{"type": "function", "function": {"name": "get_weather", "description": "Get weather", "parameters": {}}}]
        
        # ASIF: The current implementation of SiliconLifeLLM returns the raw JSON string of the entire response
        # if tools are present and it can't find a direct text response.
        # This might not be the desired final behavior (which would be to parse and return a dict like OpenAI).
        # This test will verify the current behavior.
        response = self.llm.generate_response(messages=self.messages, tools=tools)

        expected_url = self.config.silicon_life_base_url
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], expected_url)
        
        payload = json.loads(kwargs['data'])
        self.assertEqual(payload['tools'], tools)
        self.assertEqual(payload['tool_choice'], "auto") # Default

        # The current code returns the json.dumps of the whole response_data if tools are present
        # and it doesn't find simple text content.
        # This needs clarification from the ASIF comments in the LLM code.
        # "return json.dumps(response_data) # Or process into a dict for tool calls"
        # For now, testing current behavior:
        self.assertEqual(response, json.dumps(mock_api_response))


class TestDeepseekLLM(unittest.TestCase):
    def setUp(self):
        self.config = BaseLlmConfig(
            api_key="test_deepseek_api_key",
            model="deepseek-test-model",
            deepseek_base_url="https://mock.api.deepseek.com/v1/chat/completions",
            temperature=0.5,
            max_tokens=100,
            top_p=0.9
        )
        self.llm = DeepseekLLM(config=self.config)
        self.messages = [{"role": "user", "content": "Hello Deepseek"}]

    @patch('requests.post')
    def test_generate_response_success(self, mock_post):
        mock_response_data = {"choices": [{"message": {"content": "Test Deepseek Response"}}]}
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.json.return_value = mock_response_data
        mock_post.return_value.raise_for_status = MagicMock()

        response = self.llm.generate_response(messages=self.messages)

        expected_url = self.config.deepseek_base_url
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], expected_url)
        self.assertEqual(kwargs['headers']['Authorization'], f"Bearer {self.config.api_key}")
        
        payload = json.loads(kwargs['data'])
        self.assertEqual(payload['model'], self.config.model)
        self.assertEqual(payload['messages'], self.messages)
        self.assertEqual(payload['temperature'], self.config.temperature)
        self.assertEqual(payload['max_tokens'], self.config.max_tokens)
        self.assertEqual(payload['top_p'], self.config.top_p)
        
        self.assertEqual(response, "Test Deepseek Response")

    @patch('requests.post')
    def test_generate_response_api_error(self, mock_post):
        mock_post.return_value = MagicMock(status_code=500)
        mock_post.return_value.raise_for_status.side_effect = requests.exceptions.HTTPError("API Error")

        with self.assertRaises(ConnectionError) as context:
            self.llm.generate_response(messages=self.messages)
        
        self.assertTrue("Failed to connect to DeepseekLLM API" in str(context.exception))
        mock_post.assert_called_once()

    @patch('requests.post')
    def test_generate_response_with_tool_call_success(self, mock_post):
        mock_tool_call = {
            "id": "call_xyz789",
            "function": {
                "name": "get_stock_price",
                "arguments": json.dumps({"ticker": "DS"}) # Arguments are a JSON string
            },
            "type": "function"
        }
        # DeepseekLLM implementation returns json.dumps({"tool_calls": message["tool_calls"]})
        mock_api_response = {"choices": [{"message": {"tool_calls": [mock_tool_call]}}]}

        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.json.return_value = mock_api_response
        mock_post.return_value.raise_for_status = MagicMock()

        tools = [{"type": "function", "function": {"name": "get_stock_price", "description": "Get stock price", "parameters": {}}}]
        
        response = self.llm.generate_response(messages=self.messages, tools=tools)

        expected_url = self.config.deepseek_base_url
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], expected_url)
        
        payload = json.loads(kwargs['data'])
        self.assertEqual(payload['tools'], tools)
        self.assertEqual(payload['tool_choice'], "auto")

        # DeepseekLLM implementation specifically extracts and returns tool_calls as JSON string
        expected_tool_call_output = json.dumps({"tool_calls": [mock_tool_call]})
        self.assertEqual(response, expected_tool_call_output)

if __name__ == '__main__':
    unittest.main()
