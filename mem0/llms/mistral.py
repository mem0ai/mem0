import json
import logging
import os
from typing import Dict, List, Optional

try:
    from mistralai.client import Mistral
except ImportError:
    raise ImportError("The 'mistralai' library is required. Please install it using 'pip install mistralai'.")

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.base import LLMBase
from mem0.memory.utils import extract_json

logger = logging.getLogger(__name__)


class MistralLLM(LLMBase):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config)

        if not self.config.model:
            self.config.model = "mistral-small-latest"

        api_key = self.config.api_key or os.getenv("MISTRAL_API_KEY")
        self.client = Mistral(api_key=api_key)

    @staticmethod
    def _convert_content_to_string(content):
        """Reasoning models return content as a list of chunks, not a string; keep only the text ones."""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(getattr(chunk, "text", "") for chunk in content if getattr(chunk, "type", None) == "text")
        return str(content) if content is not None else ""

    def _parse_response(self, response, tools):
        """
        Process the response based on whether tools are used or not.

        Args:
            response: The raw response from the Mistral API.
            tools: The list of tools provided in the request.

        Returns:
            str or dict: The processed response.
        """
        if tools:
            processed_response = {
                "content": self._convert_content_to_string(response.choices[0].message.content),
                "tool_calls": [],
            }

            if response.choices[0].message.tool_calls:
                for tool_call in response.choices[0].message.tool_calls:
                    arguments = tool_call.function.arguments
                    # arguments can be a dict already, not always a JSON string
                    if isinstance(arguments, str):
                        arguments = json.loads(extract_json(arguments))
                    processed_response["tool_calls"].append(
                        {
                            "name": tool_call.function.name,
                            "arguments": arguments,
                        }
                    )

            return processed_response
        else:
            return self._convert_content_to_string(response.choices[0].message.content)

    def generate_response(
        self,
        messages: List[Dict[str, str]],
        response_format=None,
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
        **kwargs,
    ):
        """
        Generate a response based on the given messages using Mistral.

        Args:
            messages (list): List of message dicts containing 'role' and 'content'.
            response_format (str or object, optional): Format of the response. Defaults to None.
            tools (list, optional): List of tools that the model can call. Defaults to None.
            tool_choice (str, optional): Tool choice method. Defaults to "auto".
            **kwargs: Additional provider-specific parameters forwarded to the Mistral
                client (matches the ``LLMBase.generate_response`` contract).

        Returns:
            str or dict: The generated response.
        """
        params = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "top_p": self.config.top_p,
        }
        # sent as-is; Mistral does no client-side model gating for this param
        reasoning_effort = getattr(self.config, "reasoning_effort", None)
        if reasoning_effort:
            params["reasoning_effort"] = reasoning_effort
        params.update(kwargs)
        if response_format:
            params["response_format"] = response_format
        if tools:
            params["tools"] = tools
            params["tool_choice"] = tool_choice

        response = self.client.chat.complete(**params)
        return self._parse_response(response, tools)
