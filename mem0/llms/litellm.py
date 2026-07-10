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

        if not self.config.model:
            self.config.model = "gpt-5-mini"

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
        if tools and not litellm.supports_function_calling(self.config.model):
            raise ValueError(f"Model '{self.config.model}' in litellm does not support function calling.")

        # Build provider params through the shared helper so reasoning models
        # (o1/o3/gpt-5 family) drop temperature/top_p the way OpenAI/xAI do.
        # LiteLLM previously always forwarded temperature, which is the same
        # failure mode documented in #6085 for the OpenAI default path.
        kwargs = {}
        if response_format:
            kwargs["response_format"] = response_format
        if tools:  # TODO: Remove tools if no issues found with new memory addition logic
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice

        params = self._get_supported_params(messages=messages, **kwargs)
        params.update(
            {
                "model": self.config.model,
                "messages": messages,
            }
        )
        # ``_get_supported_params`` already chose max_tokens vs max_completion_tokens
        # for non-reasoning models. For reasoning models the shared helper omits the
        # cap entirely today; re-apply the GPT-5-family max_completion_tokens key so
        # configured limits still work through LiteLLM.
        if self._is_reasoning_model(self.config.model) or self._uses_max_completion_tokens(
            self.config.model
        ):
            if self.config.max_tokens is not None and "max_tokens" not in params and "max_completion_tokens" not in params:
                params["max_completion_tokens"] = self.config.max_tokens
        params.setdefault("model", self.config.model)

        response = litellm.completion(**params)
        return self._parse_response(response, tools)
