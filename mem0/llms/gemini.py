import os
from typing import Dict, List, Optional

try:
    import google.genai as genai
    from google.genai.types import content_types
except ImportError:
    raise ImportError(
        "The 'google-genai' library is required. Please install it using 'pip install google-genai'."
    )

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.base import LLMBase


class GeminiLLM(LLMBase):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config)

        if not self.config.model:
            self.config.model = "gemini-2.0-flash-lite"

        api_key = self.config.api_key or os.getenv("GEMINI_API_KEY")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name=self.config.model)

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
                "content": response.text,
                "tool_calls": [],
            }

            if response.candidates and response.candidates[0].content:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'function_call'):
                        fn_call = part.function_call
                        processed_response["tool_calls"].append({
                            "name": fn_call.name,
                            "arguments": fn_call.args
                        })

            return processed_response
        else:
            return response.text

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

            new_messages.append(
                {
                    "role": "model" if message["role"] == "model" else "user",
                    "parts": [{"text": content}]
                }
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
        if not tools:
            return None

        new_tools = []
        for tool in tools:
            func = tool["function"].copy()
            # Remove any additionalProperties as they're not supported
            if "additionalProperties" in func:
                del func["additionalProperties"]
            new_tools.append({"function_declarations": [func]})

        return new_tools

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
        generation_config = {
            "temperature": self.config.temperature,
            "max_output_tokens": self.config.max_tokens,
            "top_p": self.config.top_p,
        }

        if response_format is not None and response_format["type"] == "json_object":
            generation_config["response_mime_type"] = "application/json"
            if "schema" in response_format:
                generation_config["response_schema"] = response_format["schema"]

        tool_config = None
        if tools:
            tool_config = {
                "function_calling_config": {
                    "mode": tool_choice,
                    "allowed_function_names": (
                        [tool["function"]["name"] for tool in tools] if tool_choice == "any" else None
                    ),
                }
            }

        response = self.model.generate_content(
            contents=self._reformat_messages(messages),
            tools=self._reformat_tools(tools),
            generation_config=generation_config,
            tool_config=tool_config,
        )

        return self._parse_response(response, tools)
