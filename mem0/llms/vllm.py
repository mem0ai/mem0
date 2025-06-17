import json
import os
from typing import Dict, List, Optional

try:
    from openai import OpenAI
except ImportError:
    raise ImportError("The 'openai' library is required for vLLM. Please install it using 'pip install openai'.")

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.base import LLMBase


class VllmLLM(LLMBase):
    """
    vLLM provider for mem0 using OpenAI-compatible API.

    Supports high-performance local inference with vLLM server.
    Requires vLLM server running with OpenAI-compatible endpoints.
    """

    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config)

        # Set default model if not provided (following pattern of other providers)
        if not self.config.model:
            self.config.model = "meta-llama/Llama-3.1-8B-Instruct"

        # Support environment variables for API key and base URL
        self.config.api_key = self.config.api_key or os.getenv("VLLM_API_KEY") or "vllm-api-key"
        vllm_base_url = self.config.vllm_base_url or os.getenv("VLLM_BASE_URL") or "http://localhost:8000/v1"

        # Initialize OpenAI client pointing to vLLM server
        self.client = OpenAI(
            base_url=vllm_base_url,
            api_key=self.config.api_key
        )

    def _parse_response(self, response, tools):
        """
        Process the response based on whether tools are used or not.

        Args:
            response: The raw response from vLLM API
            tools: The list of tools provided in the request

        Returns:
            str or dict: The processed response
        """
        if tools:
            processed_response = {
                "content": response.choices[0].message.content,
                "tool_calls": [],
            }

            if response.choices[0].message.tool_calls:
                for tool_call in response.choices[0].message.tool_calls:
                    processed_response["tool_calls"].append({
                        "name": tool_call.function.name,
                        "arguments": json.loads(tool_call.function.arguments),
                    })

            return processed_response
        else:
            return response.choices[0].message.content

    def generate_response(
        self,
        messages: List[Dict[str, str]],
        response_format=None,
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
    ):
        """
        Generate a response using vLLM server.

        Args:
            messages (list): List of message dicts containing 'role' and 'content'
            response_format (str or object, optional): Format of the response
            tools (list, optional): List of tools that the model can call
            tool_choice (str, optional): Tool choice method

        Returns:
            str: The generated response
        """
        params = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "top_p": self.config.top_p,
        }

        if response_format:
            params["response_format"] = response_format

        if tools:
            params["tools"] = tools
            params["tool_choice"] = tool_choice

        response = self.client.chat.completions.create(**params)
        return self._parse_response(response, tools)
