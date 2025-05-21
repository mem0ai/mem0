import json
import requests
from typing import Dict, List, Optional

from mem0.llms.base import LLMBase
from mem0.configs.llms.base import BaseLlmConfig


class DeepseekLLM(LLMBase):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config)
        # Deepseek specific base URL is available in config
        self.endpoint_url = self.config.deepseek_base_url or "https://api.deepseek.com/chat/completions"
        if not self.config.deepseek_base_url:
            # ASIF: Comment that we are falling back to a default if not provided in config.
            print("Warning: Deepseek base URL not configured, using default.")


    def generate_response(self, messages: List[Dict], tools: Optional[List[Dict]] = None, tool_choice: str = "auto"):
        """
        Generate a response based on the given messages using DeepseekLLM.

        Args:
            messages (list): List of message dicts containing 'role' and 'content'.
            tools (list, optional): List of tools that the model can call. Defaults to None.
            tool_choice (str, optional): Tool choice method. Defaults to "auto".

        Returns:
            str: The generated response text.
        """
        if not self.config.api_key:
            raise ValueError("API key for DeepseekLLM is not configured.")

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        # ASIF: The payload structure is based on common LLM APIs like OpenAI.
        # Verify with Deepseek API documentation.
        # A previous version of DeepSeekLLM existed; its payload structure might be a reference.
        payload = {
            "model": self.config.model or "deepseek-chat", # ASIF: Default model name is assumed
            "messages": messages,
        }
        if tools:
            # ASIF: How tools are passed to Deepseek API is an assumption.
            # Check if this aligns with the previous DeepSeekLLM implementation or official docs.
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice
        
        # ASIF: Add other parameters like temperature, max_tokens from self.config if applicable
        if self.config.temperature is not None:
            payload["temperature"] = self.config.temperature
        if self.config.max_tokens is not None:
            payload["max_tokens"] = self.config.max_tokens
        if self.config.top_p is not None:
            payload["top_p"] = self.config.top_p


        try:
            response = requests.post(self.endpoint_url, headers=headers, data=json.dumps(payload))
            response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
        except requests.exceptions.RequestException as e:
            # ASIF: More specific error handling might be needed.
            raise ConnectionError(f"Failed to connect to DeepseekLLM API: {e}")

        try:
            response_data = response.json()
            # ASIF: The path to the response text is assumed based on common patterns (OpenAI-like).
            # Verify with Deepseek API documentation.
            # The previous DeepSeekLLM implementation might have had a _parse_response method.
            if "choices" in response_data and response_data["choices"]:
                message = response_data["choices"][0].get("message", {})
                if "content" in message and message["content"] is not None: # Check for non-null content
                    return message["content"]
                # ASIF: Handling for tool calls if present, similar to OpenAI.
                # This part needs to be verified against how Deepseek API returns tool calls
                # and how mem0 expects them (e.g., a dict).
                # The method signature currently returns str, which is limiting for tool calls.
                # If tool_calls are present, the method should ideally return a dict.
                if "tool_calls" in message and message["tool_calls"]:
                    # ASIF: Placeholder for tool call response processing.
                    # This should return a dictionary if tools are used.
                    # For now, returning the JSON string of the tool_calls part or the whole message.
                    # This is a known deviation if parsed tool calls are expected.
                    return json.dumps({"tool_calls": message["tool_calls"]}) # Or process appropriately

            # ASIF: Fallback for other possible response structures.
            elif "response" in response_data:
                return response_data["response"]
            
            # If no text content and no tool_calls, this indicates an unexpected format or empty response.
            raise ValueError(f"No content or tool_calls found in DeepseekLLM response: {response_data}")

        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as e: # Added TypeError for message.get
            # ASIF: More specific error handling might be needed.
            raise ValueError(f"Failed to parse response from DeepseekLLM API: {e} - Response: {response.text}")

        # Fallback if the structure was not recognized
        raise ValueError(f"Could not extract content or tool_calls from DeepseekLLM response: {response.text}")
