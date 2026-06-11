import os
from typing import Dict, List, Optional, Union

try:
    import anthropic
except ImportError:
    raise ImportError("The 'anthropic' library is required. Please install it using 'pip install anthropic'.")

from mem0.configs.llms.anthropic import AnthropicConfig
from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.base import LLMBase


class AnthropicLLM(LLMBase):
    supports_tool_calls = True

    def __init__(self, config: Optional[Union[BaseLlmConfig, AnthropicConfig, Dict]] = None):
        # Convert to AnthropicConfig if needed
        if config is None:
            config = AnthropicConfig()
        elif isinstance(config, dict):
            config = AnthropicConfig(**config)
        elif isinstance(config, BaseLlmConfig) and not isinstance(config, AnthropicConfig):
            # Convert BaseLlmConfig to AnthropicConfig
            config = AnthropicConfig(
                model=config.model,
                temperature=config.temperature,
                api_key=config.api_key,
                max_tokens=config.max_tokens,
                top_p=config.top_p,
                top_k=config.top_k,
                enable_vision=config.enable_vision,
                vision_details=config.vision_details,
                http_client_proxies=config.http_client,
            )

        super().__init__(config)

        if not self.config.model:
            self.config.model = "claude-3-5-sonnet-20240620"

        api_key = self.config.api_key or os.getenv("ANTHROPIC_API_KEY")
        self.client = anthropic.Anthropic(api_key=api_key)

    def _get_common_params(self, **kwargs) -> Dict:
        """Get common parameters, avoiding sending both temperature and top_p together.

        Anthropic rejects requests that include both temperature and top_p.
        When both are set, we keep temperature and drop top_p.
        """
        params = {}

        if self.config.max_tokens is not None:
            params["max_tokens"] = self.config.max_tokens

        has_temperature = self.config.temperature is not None
        has_top_p = self.config.top_p is not None

        if has_temperature and has_top_p:
            # Anthropic forbids both; prefer temperature
            params["temperature"] = self.config.temperature
        elif has_temperature:
            params["temperature"] = self.config.temperature
        elif has_top_p:
            params["top_p"] = self.config.top_p

        params.update(kwargs)
        return params

    @staticmethod
    def _convert_tools(tools: List[Dict]) -> List[Dict]:
        """Convert OpenAI function-calling tool schemas to Anthropic's format.

        mem0 defines tools in OpenAI format ({"type": "function", "function":
        {"name", "description", "parameters"}}); Anthropic expects flat tools
        with an ``input_schema``. Tools already in Anthropic format (carrying
        ``input_schema``) are passed through unchanged.
        """
        converted = []
        for tool in tools:
            if "input_schema" in tool:
                converted.append(tool)
                continue
            function = tool.get("function", tool)
            converted.append(
                {
                    "name": function.get("name"),
                    "description": function.get("description", ""),
                    "input_schema": function.get("parameters", {"type": "object", "properties": {}}),
                }
            )
        return converted

    @staticmethod
    def _convert_tool_choice(tool_choice):
        """Map the cross-provider ``tool_choice`` value to Anthropic's format.

        Anthropic expects a dict ({"type": "auto" | "any" | "none" | "tool"}).
        Accepts the OpenAI-style strings used across mem0 ("auto", "required",
        "none") and a bare tool name to force a specific tool; an already-formed
        dict is passed through.
        """
        if isinstance(tool_choice, dict):
            return tool_choice
        mapping = {
            "auto": {"type": "auto"},
            "required": {"type": "any"},
            "any": {"type": "any"},
            "none": {"type": "none"},
        }
        if tool_choice in mapping:
            return mapping[tool_choice]
        # Anything else is treated as a specific tool name to force.
        return {"type": "tool", "name": tool_choice}

    @staticmethod
    def _parse_response(response, tools):
        """Process the Anthropic response based on whether tools were used.

        With tools, returns the same shape as the OpenAI provider -
        ``{"content": <text>, "tool_calls": [{"name", "arguments"}]}`` - reading
        the JSON out of each ``tool_use`` block's ``.input`` (the SDK already
        parses it to a dict). Without tools, returns the assistant text, or ""
        when the response carries no content blocks (e.g. blocked/refused).
        """
        if tools:
            processed_response = {"content": None, "tool_calls": []}
            for block in response.content:
                block_type = getattr(block, "type", None)
                if block_type == "text":
                    processed_response["content"] = block.text
                elif block_type == "tool_use":
                    processed_response["tool_calls"].append({"name": block.name, "arguments": block.input})
            return processed_response

        return response.content[0].text if response.content else ""

    def generate_response(
        self,
        messages: List[Dict[str, str]],
        response_format=None,
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
        **kwargs,
    ):
        """
        Generate a response based on the given messages using Anthropic.

        Args:
            messages (list): List of message dicts containing 'role' and 'content'.
            response_format (str or object, optional): Format of the response. Defaults to "text".
            tools (list, optional): List of tools that the model can call. Defaults to None.
            tool_choice (str, optional): Tool choice method. Defaults to "auto".
            **kwargs: Additional Anthropic-specific parameters.

        Returns:
            str or dict: The assistant text, or, when ``tools`` are supplied, a
            ``{"content", "tool_calls"}`` dict matching the other providers.
        """
        # Separate system message from other messages
        system_message = ""
        filtered_messages = []
        for message in messages:
            if message["role"] == "system":
                system_message = message["content"]
            else:
                filtered_messages.append(message)

        params = self._get_supported_params(messages=messages, **kwargs)
        params.update(
            {
                "model": self.config.model,
                "messages": filtered_messages,
                "system": system_message,
            }
        )

        if tools:
            params["tools"] = self._convert_tools(tools)
            params["tool_choice"] = self._convert_tool_choice(tool_choice)

        response = self.client.messages.create(**params)
        return self._parse_response(response, tools)
