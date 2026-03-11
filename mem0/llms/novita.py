import json
import logging
import os
import warnings
from typing import Dict, List, Optional, Union

from openai import OpenAI

from mem0.configs.llms.base import BaseLlmConfig
from mem0.configs.llms.novita import NovitaConfig
from mem0.llms.base import LLMBase
from mem0.memory.utils import extract_json


class NovitaLLM(LLMBase):
    def __init__(self, config: Optional[Union[BaseLlmConfig, NovitaConfig, Dict]] = None):
        # Convert to NovitaConfig if needed
        if config is None:
            config = NovitaConfig()
        elif isinstance(config, dict):
            config = NovitaConfig(**config)
        elif isinstance(config, BaseLlmConfig) and not isinstance(config, NovitaConfig):
            # Convert BaseLlmConfig to NovitaConfig
            config = NovitaConfig(
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
            self.config.model = "deepseek/deepseek-v3.2"

        if os.environ.get("NOVITA_API_BASE"):
            warnings.warn(
                "The environment variable 'NOVITA_API_BASE' is deprecated and will be removed in a future version. "
                "Please use 'NOVITA_API_URL' instead.",
                DeprecationWarning,
            )

        api_key = self.config.api_key or os.getenv("NOVITA_API_KEY")
        base_url = (
            self.config.novita_base_url
            or os.getenv("NOVITA_API_URL")
            or os.getenv("NOVITA_API_BASE")
            or "https://api.novita.ai/openai"
        )
        self.client = OpenAI(api_key=api_key, base_url=base_url)

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
        **kwargs,
    ):
        """
        Generate a response based on the given messages using Novita.

        Args:
            messages (list): List of message dicts containing 'role' and 'content'.
            response_format (str or object, optional): Format of the response. Defaults to "text".
            tools (list, optional): List of tools that the model can call. Defaults to None.
            tool_choice (str, optional): Tool choice method. Defaults to "auto".
            **kwargs: Additional Novita-specific parameters.

        Returns:
            str: The generated response.
        """
        params = self._get_supported_params(messages=messages, **kwargs)
        params.update(
            {
                "model": self.config.model,
                "messages": messages,
            }
        )

        if response_format:
            params["response_format"] = response_format
        if tools:
            params["tools"] = tools
            params["tool_choice"] = tool_choice

        response = self.client.chat.completions.create(**params)
        parsed_response = self._parse_response(response, tools)
        if self.config.response_callback:
            try:
                self.config.response_callback(self, response, params)
            except Exception as e:
                logging.error(f"Error due to callback: {e}")
                pass
        return parsed_response
