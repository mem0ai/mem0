import json
import requests
from typing import Dict, List, Optional

from mem0.llms.base import LLMBase
from mem0.configs.llms.base import BaseLlmConfig


class SiliconLifeLLM(LLMBase):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config)
        # ASIF: The actual endpoint for SiliconLifeLLM needs to be configured.
        # It might be part of self.config or a dedicated environment variable.
        # For now, using a placeholder.
        self.endpoint_url = getattr(self.config, 'silicon_life_base_url', "https://api.siliconlife.ai/v1/chat/completions")


    def generate_response(self, messages: List[Dict], tools: Optional[List[Dict]] = None, tool_choice: str = "auto"):
        """
        Generate a response based on the given messages using SiliconLifeLLM.

        Args:
            messages (list): List of message dicts containing 'role' and 'content'.
            tools (list, optional): List of tools that the model can call. Defaults to None.
            tool_choice (str, optional): Tool choice method. Defaults to "auto".

        Returns:
            str: The generated response text.
        """
        if not self.config.api_key:
            raise ValueError("API key for SiliconLifeLLM is not configured.")

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        # ASIF: The payload structure is assumed.
        # Verify with SiliconLife API documentation.
        payload = {
            "model": self.config.model or "default-siliconlife-model", # ASIF: Default model name is assumed
            "messages": messages,
            # ASIF: tool and tool_choice parameters might need specific handling
            # based on SiliconLife API. For now, they are not included in the payload.
        }
        if tools:
            # ASIF: How tools are passed to SiliconLife API is an assumption.
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice


        try:
            response = requests.post(self.endpoint_url, headers=headers, data=json.dumps(payload))
            response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
        except requests.exceptions.RequestException as e:
            # ASIF: More specific error handling might be needed.
            raise ConnectionError(f"Failed to connect to SiliconLifeLLM API: {e}")

        try:
            response_data = response.json()
            # ASIF: The path to the response text is assumed.
            # Verify with SiliconLife API documentation.
            # Example: response_data['choices'][0]['message']['content']
            # For now, assuming a simple structure like: {"response": "text"} or handling common alternatives
            if "choices" in response_data and response_data["choices"]:
                message = response_data["choices"][0].get("message", {})
                if "content" in message:
                    return message["content"]
            elif "response" in response_data: # Fallback for a simpler structure
                return response_data["response"]
            
            # ASIF: If the response structure for tool calls is different, this needs adjustment.
            # For now, returning the full content if it's not a simple text response.
            # This part needs to align with how mem0 expects tool call responses.
            # The base class _parse_response in the previous DeepSeekLLM might be a reference
            # if tool calls are handled by returning a dict.
            # Given the current method signature returns a string, this might imply only text responses are expected here.
            # If tool calls are part of the response, the return type of this method might need to change.
            # For now, if it's not simple text, returning the JSON string.
            if not isinstance(response_data, str): # Check if it's not already a string
                 # ASIF: This part needs to be confirmed. If tool calls are expected,
                 # the return type should be Dict, not str.
                 # For now, assuming text response is primary.
                 if payload.get("tools"): # If tools were requested
                     # ASIF: Placeholder for tool call response processing.
                     # This should return a dictionary if tools are used, similar to OpenAI's format.
                     # For now, returning the raw JSON if it's not a simple text content.
                     # This is a known deviation if tool calls are expected to be parsed here.
                     # The method signature currently returns str, which might be limiting for tool calls.
                     return json.dumps(response_data) # Or process into a dict for tool calls
                 else: # If no tools, and not the expected text structure
                     raise ValueError(f"Unexpected response format from SiliconLifeLLM: {response_data}")


        except (json.JSONDecodeError, KeyError, IndexError) as e:
            # ASIF: More specific error handling might be needed.
            raise ValueError(f"Failed to parse response from SiliconLifeLLM API: {e} - Response: {response.text}")
        
        # Fallback if no specific content found and no tools were used
        raise ValueError(f"Could not extract content from SiliconLifeLLM response: {response.text}")
