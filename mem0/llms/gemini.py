import os
from typing import Dict, List, Optional, Union

try:
    from google import genai
    from google.genai import types
except ImportError:
    raise ImportError("The 'google-genai' library is required. Please install it using 'pip install google-genai'.")

from mem0.configs.llms.base import BaseLlmConfig
from mem0.configs.llms.gemini import GeminiConfig
from mem0.llms.base import LLMBase


class GeminiLLM(LLMBase):
    def __init__(self, config: Optional[Union[BaseLlmConfig, GeminiConfig, Dict]] = None):
        # Convert to GeminiConfig if needed
        if config is None:
            config = GeminiConfig()
        elif isinstance(config, dict):
            config = GeminiConfig(**config)
        elif isinstance(config, BaseLlmConfig) and not isinstance(config, GeminiConfig):
            config = GeminiConfig(
                model=config.model,
                temperature=config.temperature,
                api_key=config.api_key,
                max_tokens=config.max_tokens,
                top_p=config.top_p,
                top_k=config.top_k,
                enable_vision=config.enable_vision,
                vision_details=config.vision_details,
            )

        super().__init__(config)

        if not self.config.model:
            self.config.model = "gemini-2.0-flash"

        if self.config.vertexai:
            self.client = genai.Client(vertexai=True, project=self.config.project, location=self.config.location)
        else:
            api_key = self.config.api_key or os.getenv("GOOGLE_API_KEY")
            self.client = genai.Client(api_key=api_key)

    def _parse_response(self, response, tools):
        """
        Process the response based on whether tools are used or not.

        Args:
            response: The raw response from API.
            tools: The list of tools provided in the request.

        Returns:
            str or dict: The processed response.
        """
        # Get parts safely — content can be None when Gemini blocks the response
        candidate = response.candidates[0] if response.candidates else None
        parts = candidate.content.parts if candidate and candidate.content else None

        if tools:
            processed_response = {
                "content": None,
                "tool_calls": [],
            }

            if parts:
                # Extract content from the first candidate
                for part in parts:
                    if hasattr(part, "text") and part.text:
                        processed_response["content"] = part.text
                        break

                # Extract function calls
                for part in parts:
                    if hasattr(part, "function_call") and part.function_call:
                        fn = part.function_call
                        processed_response["tool_calls"].append(
                            {
                                "name": fn.name,
                                "arguments": dict(fn.args) if fn.args else {},
                            }
                        )

            return processed_response
        else:
            if parts:
                for part in parts:
                    if hasattr(part, "text") and part.text:
                        return part.text
            return ""

    def _reformat_messages(self, messages: List[Dict[str, str]]):
        """
        Reformat messages for Gemini.

        Args:
            messages: The list of messages provided in the request.

        Returns:
            tuple: (system_instruction, contents_list)
        """
        system_instruction = None
        contents = []

        for message in messages:
            if message["role"] == "system":
                system_instruction = message["content"]
            else:
                content = types.Content(
                    parts=[types.Part(text=message["content"])],
                    role=message["role"],
                )
                contents.append(content)

        return system_instruction, contents

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

        if tools:
            function_declarations = []
            for tool in tools:
                func = tool["function"].copy()
                cleaned_func = remove_additional_properties(func)

                function_declaration = types.FunctionDeclaration(
                    name=cleaned_func["name"],
                    description=cleaned_func.get("description", ""),
                    parameters=cleaned_func.get("parameters", {}),
                )
                function_declarations.append(function_declaration)

            tool_obj = types.Tool(function_declarations=function_declarations)
            return [tool_obj]
        else:
            return None

    def generate_response(
        self,
        messages: List[Dict[str, str]],
        response_format=None,
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
        **kwargs,
    ):
        """
        Generate a response based on the given messages using Gemini.

        Args:
            messages (list): List of message dicts containing 'role' and 'content'.
            response_format (str or object, optional): Format for the response. Defaults to "text".
            tools (list, optional): List of tools that the model can call. Defaults to None.
            tool_choice (str, optional): Tool choice method, one of "auto", "any",
                "required", or "none". "required" is treated as "any" (force a tool
                call). Defaults to "auto".
            **kwargs: Additional per-call overrides (e.g. ``max_tokens``,
                ``temperature``, ``top_p``) that take precedence over configured
                defaults. Unknown kwargs are ignored.

        Returns:
            str: The generated response.
        """

        # Extract system instruction and reformat messages
        system_instruction, contents = self._reformat_messages(messages)

        # Prepare generation config — only include non-None values so the
        # Gemini SDK uses its own defaults instead of rejecting None.
        # Per-call kwargs override configured defaults; note Gemini names the
        # token limit ``max_output_tokens``.
        temperature = kwargs.get("temperature", self.config.temperature)
        max_tokens = kwargs.get("max_tokens", self.config.max_tokens)
        top_p = kwargs.get("top_p", self.config.top_p)
        config_params = {}
        if temperature is not None:
            config_params["temperature"] = temperature
        if max_tokens is not None:
            config_params["max_output_tokens"] = max_tokens
        if top_p is not None:
            config_params["top_p"] = top_p

        # Add system instruction to config if present
        if system_instruction:
            config_params["system_instruction"] = system_instruction

        if response_format is not None and response_format["type"] == "json_object":
            config_params["response_mime_type"] = "application/json"
            if "schema" in response_format:
                config_params["response_schema"] = response_format["schema"]

        if tools:
            formatted_tools = self._reformat_tools(tools)
            config_params["tools"] = formatted_tools

            if tool_choice:
                if tool_choice in ("any", "required"):
                    # Both mean "the model must call a tool" -> Gemini ANY mode.
                    mode = types.FunctionCallingConfigMode.ANY
                elif tool_choice == "none":
                    mode = types.FunctionCallingConfigMode.NONE
                else:
                    # "auto" or any unrecognized value: let the model decide.
                    mode = types.FunctionCallingConfigMode.AUTO

                tool_config = types.ToolConfig(
                    function_calling_config=types.FunctionCallingConfig(
                        mode=mode,
                        # Constrain to the provided tool names only when forcing a call.
                        allowed_function_names=(
                            [tool["function"]["name"] for tool in tools]
                            if tool_choice in ("any", "required")
                            else None
                        ),
                    )
                )
                config_params["tool_config"] = tool_config

        generation_config = types.GenerateContentConfig(**config_params)

        response = self.client.models.generate_content(
            model=self.config.model, contents=contents, config=generation_config
        )

        return self._parse_response(response, tools)
