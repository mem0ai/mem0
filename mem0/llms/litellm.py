import json
from typing import Dict, List, Optional

try:
    import litellm
except ImportError:
    raise ImportError("The 'litellm' library is required. Please install it using 'pip install litellm'.")

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.base import LLMBase
from mem0.memory.utils import extract_json


class LiteLLM(LLMBase):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config)

        # Handle model as string or dict
        if not self.config.model:
            self.config.model = "gpt-4.1-nano-2025-04-14"
        elif isinstance(self.config.model, dict) and not self.config.model.get("name"):
            self.config.model["name"] = "gpt-4.1-nano-2025-04-14"

    def _get_model_name(self) -> str:
        """
        Get the model name from config.
        Handles both string and dict formats for model specification.

        Returns:
            str: The model name/identifier.
        """
        if isinstance(self.config.model, dict):
            return self.config.model.get("name", "gpt-4.1-nano-2025-04-14")
        return self.config.model

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
        Generate a response based on the given messages using Litellm.

        Args:
            messages (list): List of message dicts containing 'role' and 'content'.
            response_format (str or object, optional): Format of the response. Defaults to "text".
            tools (list, optional): List of tools that the model can call. Defaults to None.
            tool_choice (str, optional): Tool choice method. Defaults to "auto".

        Returns:
            str: The generated response.

        Note:
            When model is specified as a dict, additional model-specific parameters
            can be passed (e.g., reasoning_effort for Gemini models).
            Example:
                "model": {
                    "name": "gemini/gemini-2.5-flash-preview-04-17",
                    "reasoning_effort": "low"
                }
        """
        model_name = self._get_model_name()

        if not litellm.supports_function_calling(model_name):
            raise ValueError(f"Model '{model_name}' in litellm does not support function calling.")

        params = {
            "model": model_name,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "top_p": self.config.top_p,
        }

        # Add model-specific parameters if model is specified as dict
        # Supports parameters like reasoning_effort for Gemini, frequency_penalty, etc.
        if isinstance(self.config.model, dict):
            model_specific_params = [
                "reasoning_effort",  # For Gemini models - controls thinking/reasoning level
                "frequency_penalty",
                "presence_penalty",
                "seed",
                "stop",
            ]
            for param in model_specific_params:
                if param in self.config.model:
                    params[param] = self.config.model[param]

        if response_format:
            params["response_format"] = response_format
        if tools:  # TODO: Remove tools if no issues found with new memory addition logic
            params["tools"] = tools
            params["tool_choice"] = tool_choice

        response = litellm.completion(**params)
        return self._parse_response(response, tools)
