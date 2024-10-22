import os
from typing import Dict, List, Optional

try:
    import google.generativeai as genai
    from google.generativeai import GenerativeModel
    from google.generativeai.types import content_types
except ImportError:
    raise ImportError(
        "The 'google-generativeai' library is required. Please install it using 'pip install google-generativeai'."
    )

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.base import LLMBase


class GeminiLLM(LLMBase):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config)

        if not self.config.model:
            self.config.model = "gemini-1.5-flash-latest"

        api_key = self.config.api_key or os.getenv("GEMINI_API_KEY")
        genai.configure(api_key=api_key)
        self.client = GenerativeModel(model_name=self.config.model)

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
                "content": content if (content := response.candidates[0].content.parts[0].text) else None,
                "tool_calls": [],
            }

            for part in response.candidates[0].content.parts:
                if fn := part.function_call:
                    processed_response["tool_calls"].append(
                        {
                            "name": fn.name,
                            "arguments": {key: val for key, val in fn.args.items()},
                        }
                    )

            return processed_response
        else:
            return response.candidates[0].content.parts[0].text

    def _reformat_messages(self, messages: List[Dict[str, str]]):
        """
        Reformat messages for Gemini.

        Args:
            messages: The list of messages provided in the request.

        Returns:
            list: The list of messages in the required format.
        """
        new_messages = []

        for message in messages:
            if message["role"] == "system":
                content = "THIS IS A SYSTEM PROMPT. YOU MUST OBEY THIS: " + message["content"]

            else:
                content = message["content"]

            new_messages.append({"parts": content, "role": "model" if message["role"] == "model" else "user"})

        return new_messages

    def _reformat_tools(self, tools: Optional[List[Dict]]):
        """
        Reformat tools for Gemini.

        Args:
            tools: The list of tools provided in the request.

        Returns:
            list: The list of tools in the required format.
        """

        def remove_additional_properties(data):
            """Recursively removes 'additionalProperties' from nested dictionaries."""

            if isinstance(data, dict):
                filtered_dict = {
                    key: remove_additional_properties(value)
                    for key, value in data.items()
                    if not (key == "additionalProperties")
                }
                return filtered_dict
            else:
                return data

        new_tools = []
        if tools:
            for tool in tools:
                func = tool["function"].copy()
                new_tools.append({"function_declarations": [remove_additional_properties(func)]})

            return new_tools
        else:
            return None

    def generate_response(
        self,
        messages: List[Dict[str, str]],
        response_format=None,
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
    ):
        """
        Generate a response based on the given messages using Gemini.

        Args:
            messages (list): List of message dicts containing 'role' and 'content'.
            response_format (str or object, optional): Format for the response. Defaults to "text".
            tools (list, optional): List of tools that the model can call. Defaults to None.
            tool_choice (str, optional): Tool choice method. Defaults to "auto".

        Returns:
            str: The generated response.
        """

        params = {
            "temperature": self.config.temperature,
            "max_output_tokens": self.config.max_tokens,
            "top_p": self.config.top_p,
        }

        if response_format:
            params["response_mime_type"] = "application/json"
            params["response_schema"] = list[response_format]
        if tool_choice:
            tool_config = content_types.to_tool_config(
                {
                    "function_calling_config": {
                        "mode": tool_choice,
                        "allowed_function_names": [tool["function"]["name"] for tool in tools]
                        if tool_choice == "any"
                        else None,
                    }
                }
            )

        response = self.client.generate_content(
            contents=self._reformat_messages(messages),
            tools=self._reformat_tools(tools),
            generation_config=genai.GenerationConfig(**params),
            tool_config=tool_config,
        )

        return self._parse_response(response, tools)
