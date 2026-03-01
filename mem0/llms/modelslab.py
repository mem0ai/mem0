import json
import os
from typing import Dict, List, Optional, Union

from openai import OpenAI

from mem0.configs.llms.base import BaseLlmConfig
from mem0.configs.llms.modelslab import ModelsLabConfig
from mem0.llms.base import LLMBase
from mem0.memory.utils import extract_json


class ModelsLabLLM(LLMBase):
    """LLM provider for ModelsLab's OpenAI-compatible uncensored chat API.

    Usage::

        from mem0 import Memory

        config = {
            "llm": {
                "provider": "modelslab",
                "config": {
                    "model": "meta-llama/Meta-Llama-3-8B-Instruct",
                    "api_key": "your-modelslab-api-key",
                    "temperature": 0.1,
                    "max_tokens": 2000,
                }
            }
        }
        m = Memory.from_config(config)

    Docs: https://docs.modelslab.com
    API key: https://modelslab.com/account/api-key
    """

    def __init__(self, config: Optional[Union[BaseLlmConfig, ModelsLabConfig, Dict]] = None):
        if config is None:
            config = ModelsLabConfig()
        elif isinstance(config, dict):
            config = ModelsLabConfig(**config)
        elif isinstance(config, BaseLlmConfig) and not isinstance(config, ModelsLabConfig):
            config = ModelsLabConfig(
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

        self.config.model = self.config.model or "meta-llama/Meta-Llama-3-8B-Instruct"
        self.config.api_key = (
            self.config.api_key
            or os.environ.get("MODELSLAB_API_KEY")
        )

        self.client = OpenAI(
            base_url=self.config.modelslab_base_url,
            api_key=self.config.api_key,
        )

    def _parse_response(self, response, tools):
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
        return response.choices[0].message.content

    def generate_response(
        self,
        messages: List[Dict[str, str]],
        response_format=None,
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
        **kwargs,
    ):
        """Generate a response using ModelsLab's uncensored chat API.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            response_format: Response format (e.g., JSON mode).
            tools: List of tool definitions for function calling.
            tool_choice: How to select tools ("auto", "none", or specific).

        Returns:
            str or dict: The generated response content.
        """
        params = self._get_supported_params(messages=messages, **kwargs)
        params.update(
            {
                "model": self.config.model,
                "messages": messages,
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens,
            }
        )
        if response_format:
            params["response_format"] = response_format
        if tools:
            params["tools"] = tools
            params["tool_choice"] = tool_choice

        response = self.client.chat.completions.create(**params)
        return self._parse_response(response, tools)
