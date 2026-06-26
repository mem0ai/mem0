import json
import logging
import os
from typing import Dict, List, Optional, Union

try:
    from groq import Groq
except ImportError:
    raise ImportError("The 'groq' library is required. Please install it using 'pip install groq'.")

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.base import LLMBase
from mem0.memory.utils import extract_json

logger = logging.getLogger(__name__)


class GroqLLM(LLMBase):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config)

        if not self.config.model:
            self.config.model = "llama-3.3-70b-versatile"

        api_key = self.config.api_key or os.getenv("GROQ_API_KEY")
        self.client = Groq(api_key=api_key)

    @staticmethod
    def _supports_json_mode(model: Optional[Union[str, Dict]]) -> bool:
        """
        Groq's compound agentic systems (e.g. ``groq/compound``, ``groq/compound-mini``)
        do not support the JSON ``response_format`` and return empty or non-JSON content
        when it is requested. See https://console.groq.com/docs/structured-outputs.

        Non-string models (the config allows a dict) are assumed to support JSON mode,
        preserving prior behavior.
        """
        if not isinstance(model, str):
            return True
        # Strip provider prefixes (e.g. "groq/compound-mini" -> "compound-mini"),
        # mirroring the _is_reasoning_model heuristic in LLMBase, so the match
        # targets the compound family rather than any name containing the substring.
        base_model = model.lower().rsplit("/", 1)[-1]
        return not base_model.startswith("compound")

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
                "content": response.choices[0].message.content,
                "tool_calls": [],
            }

            if response.choices[0].message.tool_calls:
                for tool_call in response.choices[0].message.tool_calls:
                    processed_response["tool_calls"].append(
                        {
                            "name": tool_call.function.name,
                            "arguments": json.loads(extract_json(tool_call.function.arguments)),
                        }
                    )

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
        Generate a response based on the given messages using Groq.

        Args:
            messages (list): List of message dicts containing 'role' and 'content'.
            response_format (str or object, optional): Format of the response. Defaults to "text".
            tools (list, optional): List of tools that the model can call. Defaults to None.
            tool_choice (str, optional): Tool choice method. Defaults to "auto".

        Returns:
            str: The generated response.
        """
        params = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "top_p": self.config.top_p,
        }
        if response_format:
            requests_json = isinstance(response_format, dict) and response_format.get("type") in (
                "json_object",
                "json_schema",
            )
            if requests_json and not self._supports_json_mode(self.config.model):
                logger.debug(
                    f"Model '{self.config.model}' does not support JSON response_format; "
                    "sending the request without it."
                )
            else:
                params["response_format"] = response_format
        if tools:
            params["tools"] = tools
            params["tool_choice"] = tool_choice

        response = self.client.chat.completions.create(**params)
        return self._parse_response(response, tools)
