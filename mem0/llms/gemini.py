import os
from typing import Dict, List, Optional

try:
    import google.genai as genai # Reverted to google.genai
    from google.genai.types import ( # Reverted to google.genai.types
        Tool,
        FunctionDeclaration,
        # FunctionResponse, # Not used in current code
        GenerationConfig,
        ToolConfig,
        FunctionCallingConfig,
        # Content, Part, # Not directly instantiated, but used for structure understanding
    )
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
            self.config.model = "gemini-1.5-flash-latest"

        api_key = self.config.api_key or os.getenv("GEMINI_API_KEY")

        # Initialize genai.Client. It will use GEMINI_API_KEY from env if api_key is not provided.
        # No explicit genai.configure() needed here as Client handles it or global config is assumed.
        if api_key:
            self.client = genai.Client(api_key=api_key)
        else:
            self.client = genai.Client() # Relies on environment variable

    def _parse_response(self, response, tools):
        """
        Process the response based on whether tools are used or not.

        Args:
            response: The raw response from API.
            tools: The list of tools provided in the request.

        Returns:
            str or dict: The processed response.
        """
        text_content = None
        tool_calls = []

        # Robust check for response and candidates
        if response is None or not hasattr(response, 'candidates') or \
           not response.candidates or len(response.candidates) == 0:
            # TODO: Log this or handle appropriately
            return {"content": None, "tool_calls": []} if tools else None

        candidate = response.candidates[0]
        if candidate and hasattr(candidate, 'content') and candidate.content and \
           hasattr(candidate.content, 'parts') and candidate.content.parts:
            for part in candidate.content.parts:
                if hasattr(part, 'function_call') and part.function_call:
                    tool_calls.append({
                        "name": part.function_call.name,
                        "arguments": dict(part.function_call.args),
                    })
                elif hasattr(part, 'text') and part.text:
                    if text_content is None:
                        text_content = part.text
                    else:
                        text_content += "\n" + part.text

        if tools:
            return {
                "content": text_content,
                "tool_calls": tool_calls,
            }
        else:
            return text_content if text_content else ""

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
                content_parts = [{"text": "THIS IS A SYSTEM PROMPT. YOU MUST OBEY THIS: " + message["content"]}]
            else:
                content_parts = [{"text": message["content"]}]

            current_role = message["role"]
            if current_role == "system":
                current_role = "user"
            elif current_role == "assistant":
                current_role = "model"

            new_messages.append(
                {
                    "parts": content_parts,
                    "role": current_role,
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

        if not tools:
            return None

        reformatted_tools = []
        for tool_dict in tools:
            func_decl = FunctionDeclaration(
                name=tool_dict["function"]["name"],
                description=tool_dict["function"]["description"],
                parameters=tool_dict["function"]["parameters"],
            )
            reformatted_tools.append(Tool(function_declarations=[func_decl]))

        return reformatted_tools

    def generate_response(
        self,
        messages: List[Dict[str, str]],
        response_format=None,
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
    ):
        """
        Generate a response based on the given messages using Gemini.
        """

        generation_config_params = {
            "temperature": self.config.temperature,
            "max_output_tokens": self.config.max_tokens,
            "top_p": self.config.top_p,
        }

        if response_format and response_format.get("type") == "json_object":
            generation_config_params["response_mime_type"] = "application/json"
            if "schema" in response_format:
                generation_config_params["response_schema"] = response_format["schema"]

        generation_config = GenerationConfig(**generation_config_params)
        reformatted_tools = self._reformat_tools(tools)

        current_tool_config = None
        if reformatted_tools:
            fcc_mode_str = "AUTO"
            allowed_function_names = None
            if tool_choice == "any": fcc_mode_str = "ANY"
            elif tool_choice == "none": fcc_mode_str = "NONE"
            elif tool_choice != "auto":
                fcc_mode_str = "ANY"
                allowed_function_names = [tool_choice]

            function_calling_config_args = {"mode": fcc_mode_str.upper()}
            if allowed_function_names:
                function_calling_config_args["allowed_function_names"] = allowed_function_names
            current_tool_config = ToolConfig(
                function_calling_config=FunctionCallingConfig(**function_calling_config_args)
            )
        elif tool_choice and tool_choice.upper() == "NONE":
            current_tool_config = ToolConfig(function_calling_config=FunctionCallingConfig(mode="NONE"))
        elif not reformatted_tools and tools is None :
             current_tool_config = ToolConfig(function_calling_config=FunctionCallingConfig(mode="AUTO"))

        contents = self._reformat_messages(messages)
        response = self.client.models.generate_content(
            model=self.config.model,
            contents=contents,
            tools=reformatted_tools,
            generation_config=generation_config,
            tool_config=current_tool_config,
        )
        return self._parse_response(response, tools)
