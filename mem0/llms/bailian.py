import json
import logging
import os
from typing import Dict, List, Optional

from openai import OpenAI

from mem0.configs.llms.base import BaseLlmConfig
from mem0.configs.llms.bailian import BailianConfig
from mem0.llms.base import LLMBase
from mem0.memory.utils import extract_json

import logging

logger = logging.getLogger(__name__)


class BaiLianLLM(LLMBase):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        # Convert to BailianConfig if needed
        if config is None:
            config = BaseLlmConfig()
        elif isinstance(config, dict):
            config = BaseLlmConfig(**config)
        elif isinstance(config, BailianConfig):
            config = config
        elif isinstance(config, BaseLlmConfig) and not isinstance(config, BailianConfig):
            # Convert BaseLlmConfig to BailianConfig
            # Handle base_url parameter if it exists
            base_url = getattr(config, 'base_url', None)
            config = BailianConfig(
                model=config.model,
                temperature=config.temperature,
                api_key=config.api_key,
                max_tokens=config.max_tokens,
                top_p=config.top_p,
                top_k=config.top_k,
                enable_vision=config.enable_vision,
                vision_details=config.vision_details,
                http_client_proxies=config.http_client,
                base_url=base_url
            )

        super().__init__(config)

        if not self.config.model:
            self.config.model = os.getenv("LLM_CONFIG_MODEL") or "qwen-plus"

        api_key = (self.config.api_key
                   or os.getenv("DASHSCOPE_API_KEY")
                   or os.getenv("LLM_API_KEY"))
        base_url = (getattr(self.config, 'openai_base_url', None)
                    or os.getenv("DASHSCOPE_BASE_URL")
                    or os.getenv("LLM_BASE_URL")
                    or "https://dashscope.aliyuncs.com/compatible-mode/v1")

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
                            "arguments": json.loads(
                                extract_json(tool_call.function.arguments)
                            ),
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
        Generate a JSON response based on the given messages using OpenAI.

        Args:
            messages (list): List of message dicts containing 'role' and 'content'.
            response_format (str or object, optional): Format of the response. Defaults to "text".
            tools (list, optional): List of tools that the model can call. Defaults to None.
            tool_choice (str, optional): Tool choice method. Defaults to "auto".
            **kwargs: Additional OpenAI-specific parameters.

        Returns:
            json: The generated response.
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
        if (
            tools
        ):  # TODO: Remove tools if no issues found with new memory addition logic
            params["tools"] = tools
            params["tool_choice"] = tool_choice
        response = self.client.chat.completions.create(**params)

        logger.debug("params: \n-------------------")
        logger.debug(params["messages"])
        logger.debug("\n-------------------\n")
        parsed_response = self._parse_response(response, tools)
        logger.debug("parsed_response: \n-------------------")
        logger.debug(parsed_response)
        logger.debug("\n-------------------\n")
        return parsed_response
