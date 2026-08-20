import json
from typing import Dict, List, Optional, Union

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

        if not self.config.model:
            self.config.model = "gpt-5-mini"
        elif isinstance(self.config.model, dict) and not self.config.model.get("name"):
            self.config.model["name"] = "gpt-5-mini"

    def _get_model_name(self) -> str:
        """Return the LiteLLM model name from string or dict model config."""
        if isinstance(self.config.model, dict):
            return self.config.model.get("name", "gpt-5-mini")
        return self.config.model

    def _get_model_params(self) -> Dict[str, Union[str, float, int, List[str]]]:
        params = {}

        reasoning_effort = getattr(self.config, "reasoning_effort", None)
        if reasoning_effort is not None:
            params["reasoning_effort"] = reasoning_effort

        if isinstance(self.config.model, dict):
            for param in ["reasoning_effort", "frequency_penalty", "presence_penalty", "seed", "stop"]:
                if self.config.model.get(param) is not None:
                    params[param] = self.config.model[param]

        return params

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
        """
        model_name = self._get_model_name()

        if tools and not litellm.supports_function_calling(model_name):
            raise ValueError(f"Model '{model_name}' in litellm does not support function calling.")

        params = {
            "model": model_name,
            "messages": messages,
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
        }
        if self._uses_max_completion_tokens(model_name):
            params["max_completion_tokens"] = self.config.max_tokens
        else:
            params["max_tokens"] = self.config.max_tokens
        params.update(self._get_model_params())
        if response_format:
            params["response_format"] = response_format
        if tools:  # TODO: Remove tools if no issues found with new memory addition logic
            params["tools"] = tools
            params["tool_choice"] = tool_choice

        response = litellm.completion(**params)
        return self._parse_response(response, tools)
