import os
from typing import Dict, List, Optional, Union

try:
    import anthropic
except ImportError:
    raise ImportError("The 'anthropic' library is required. Please install it using 'pip install anthropic'.")

from mem0.configs.llms.anthropic import AnthropicConfig
from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.base import LLMBase
from mem0.memory.utils import extract_json


class AnthropicLLM(LLMBase):
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
                http_client_proxies=config.http_client_proxies,
            )

        super().__init__(config)

        if not self.config.model:
            self.config.model = "claude-sonnet-4-6"

        api_key = self.config.api_key or os.getenv("ANTHROPIC_API_KEY")
        base_url = self.config.anthropic_base_url or os.getenv("ANTHROPIC_BASE_URL")
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        self.client = anthropic.Anthropic(**client_kwargs)

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
            str: The generated response.
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

        if tools:  # TODO: Remove tools if no issues found with new memory addition logic
            params["tools"] = tools
            params["tool_choice"] = {"type": tool_choice}

        wants_json_prefill = False
        if response_format and isinstance(response_format, dict):
            format_type = response_format.get("type")
            if format_type == "json_schema" and "json_schema" in response_format:
                # Use Anthropic structured outputs via output_config
                schema = response_format["json_schema"]
                if isinstance(schema, dict) and "schema" in schema:
                    schema = schema["schema"]
                params["output_config"] = {"format": {"type": "json_schema", "schema": schema}}
            elif format_type == "json_object":
                # Use assistant prefill to guide JSON output
                wants_json_prefill = True
                json_instruction = (
                    "\n\nYou must respond with valid JSON only. "
                    "Do not include any other text, markdown formatting, or code fences."
                )
                if params.get("system"):
                    params["system"] += json_instruction
                else:
                    params["system"] = json_instruction.strip()
                params["messages"] = list(params["messages"]) + [
                    {"role": "assistant", "content": "{"}
                ]

        response = self.client.messages.create(**params)

        if wants_json_prefill:
            # Re-attach the prefilled "{" and strip any stray wrapping.
            return extract_json("{" + response.content[0].text)

        return self._parse_response(response, tools)

    def _parse_response(self, response, tools):
        if tools:
            result = {"content": None, "tool_calls": []}
            for block in response.content:
                if block.type == "text":
                    result["content"] = block.text
                elif block.type == "tool_use":
                    result["tool_calls"].append(
                        {"name": block.name, "arguments": block.input}
                    )
            return result
        return response.content[0].text
