import json
import os
from typing import Dict, List, Optional, Union

from openai import OpenAI

from mem0.configs.llms.base import BaseLlmConfig
from mem0.configs.llms.qwen import QwenConfig
from mem0.llms.base import LLMBase
from mem0.memory.utils import extract_json


class QwenLLM(LLMBase):
    def __init__(self, config: Optional[Union[BaseLlmConfig, QwenConfig, Dict]] = None):
        # Convert to QwenConfig if needed
        if config is None:
            config = QwenConfig()
        elif isinstance(config, dict):
            config = QwenConfig(**config)
        elif isinstance(config, BaseLlmConfig) and not isinstance(config, QwenConfig):
            # Convert BaseLlmConfig to QwenConfig
            config = QwenConfig(
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
            self.config.model = "qwen-turbo"

        api_key = self.config.api_key or os.getenv("DASHSCOPE_API_KEY")
        base_url = (
            self.config.qwen_base_url
            or os.getenv("DASHSCOPE_API_BASE")
            or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def _parse_response(self, response, tools):
        """
        Process the response based on whether tools are used or not.

        Args:
            response: The raw response from API.
            tools: The list of tools provided in the request.

        Returns:
            str or dict: The response content.
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
                            "arguments": json.loads(tool_call.function.arguments),
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
    ):
        """
        Generate a response based on the given messages using Qwen (DashScope).

        Args:
            messages (List[Dict[str, str]]): A list of dictionaries representing the conversation history.
            response_format: The desired format of the response. Defaults to None.
            tools (Optional[List[Dict]], optional): A list of tools that the model can use. Defaults to None.

        Returns:
            str: The generated response from the model.
        """
        params = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "top_p": self.config.top_p,
        }

        if tools:
            params["tools"] = tools

        response = self.client.chat.completions.create(**params)
        return self._parse_response(response, tools)
