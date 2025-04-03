import json
import os
from typing import Dict, List, Optional

import requests

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.base import LLMBase


class JinaLLM(LLMBase):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config)

        if not self.config.model:
            self.config.model = "jina-chat-v1"  # Default model if not specified

        self.api_key = self.config.api_key or os.getenv("JINACHAT_API_KEY")
        if not self.api_key:
            raise ValueError("Jina Chat API key is required. Set it in the config or as JINACHAT_API_KEY environment variable.")
        
        self.base_url = self.config.jina_base_url or os.getenv("JINACHAT_API_BASE") or "https://api.chat.jina.ai/v1/chat"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    def _parse_response(self, response, tools):
        """
        Process the response based on whether tools are used or not.

        Args:
            response: The raw response from API.
            tools: The list of tools provided in the request.

        Returns:
            str or dict: The processed response.
        """
        if tools:
            processed_response = {
                "content": response["choices"][0]["message"]["content"],
                "tool_calls": [],
            }

            # Check if tool_calls exists in the response
            if "tool_calls" in response["choices"][0]["message"]:
                for tool_call in response["choices"][0]["message"]["tool_calls"]:
                    processed_response["tool_calls"].append(
                        {
                            "name": tool_call["function"]["name"],
                            "arguments": json.loads(tool_call["function"]["arguments"]),
                        }
                    )

            return processed_response
        else:
            return response["choices"][0]["message"]["content"]

    def generate_response(
        self,
        messages: List[Dict[str, str]],
        response_format=None,
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
    ):
        """
        Generate a response based on the given messages using Jina AI Chat.

        Args:
            messages (list): List of message dicts containing 'role' and 'content'.
            response_format (str or object, optional): Format of the response. Defaults to None.
            tools (list, optional): List of tools that the model can call. Defaults to None.
            tool_choice (str, optional): Tool choice method. Defaults to "auto".

        Returns:
            str or dict: The generated response.
        """
        # Build the request payload
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "top_p": self.config.top_p,
        }

        # Add tools if provided
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice

        # Add response format if provided
        if response_format:
            payload["response_format"] = response_format

        # Make the API request
        try:
            response = requests.post(
                f"{self.base_url}/completions",
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            response_data = response.json()
            
            # Return parsed response
            return self._parse_response(response_data, tools)
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Error making request to Jina AI Chat API: {str(e)}"
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_response = e.response.json()
                    if isinstance(error_response, dict) and 'error' in error_response:
                        error_msg += f". API Error: {error_response['error']}"
                except (ValueError, AttributeError, TypeError):
                    if hasattr(e.response, 'status_code'):
                        error_msg += f". Status code: {e.response.status_code}"
            raise Exception(error_msg) 