import os
from typing import Dict, List, Optional

try:
    from google import genai
    from google.genai import types

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
        self.client_gemini = genai.Client(
            api_key=api_key,
        )

    def _parse_response(self, response, tools):
        """
        Process the response based on whether tools are used or not.

        Args:
            response: The raw response from the API.
            tools: The list of tools provided in the request.

        Returns:
            str or dict: The processed response.
        """
        candidate = response.candidates[0]
        content = candidate.content.parts[0].text if candidate.content.parts else None

        if tools:
            processed_response = {
                "content": content,
                "tool_calls": [],
            }

            for part in candidate.content.parts:
                fn = getattr(part, "function_call", None)
                if fn:
                    processed_response["tool_calls"].append(
                        {
                            "name": fn.name,
                            "arguments": fn.args,
                        }
                    )

            return processed_response

        return content

    def _reformat_messages(self, messages: List[Dict[str, str]]) -> List[types.Content]:
        """
        Reformat messages for Gemini using google.genai.types.

        Args:
            messages: The list of messages provided in the request.

        Returns:
            list: A list of types.Content objects with proper role and parts.
        """
        new_messages = []

        for message in messages:
            if message["role"] == "system":
                content = "THIS IS A SYSTEM PROMPT. YOU MUST OBEY THIS: " + message["content"]
            else:
                content = message["content"]

            new_messages.append(
                types.Content(role="model" if message["role"] == "model" else "user", parts=[types.Part(text=content)])
            )

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

            # TODO: temporarily ignore it to pass tests, will come back to update according to standards later.
            # return content_types.to_function_library(new_tools)

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

        if response_format is not None and response_format["type"] == "json_object":
            params["response_mime_type"] = "application/json"
            if "schema" in response_format:
                params["response_schema"] = response_format["schema"]

        tool_config = None
        if tool_choice:
            tool_config = types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode=tool_choice.upper(),  # Assuming 'any' should become 'ANY', etc.
                    allowed_function_names=[tool["function"]["name"] for tool in tools]
                    if tool_choice == "any"
                    else None,
                )
            )

        response = self.client_gemini.models.generate_content(
            model=self.config.model,
            contents=self._reformat_messages(messages),
            config=types.GenerateContentConfig(
                temperature=self.config.temperature,
                max_output_tokens=self.config.max_tokens,
                top_p=self.config.top_p,
                tools=self._reformat_tools(tools),
                tool_config=tool_config,
            ),
        )

        return self._parse_response(response, tools)
