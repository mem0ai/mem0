import json
import os
from typing import Dict, List, Optional, Union

from openai import OpenAI

from mem0.configs.llms.base import BaseLlmConfig
from mem0.configs.llms.zhipu import ZhipuConfig
from mem0.llms.base import LLMBase
from mem0.memory.utils import extract_json


class ZhipuLLM(LLMBase):
    def __init__(self, config: Optional[Union[BaseLlmConfig, ZhipuConfig, Dict]] = None):
        if config is None:
            config = ZhipuConfig()
        elif isinstance(config, dict):
            config = ZhipuConfig(**config)
        elif isinstance(config, BaseLlmConfig) and not isinstance(config, ZhipuConfig):
            config = ZhipuConfig(
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
            self.config.model = "glm-4-plus"

        api_key = self.config.api_key or os.getenv("ZHIPU_API_KEY")
        base_url = self.config.zhipu_base_url or os.getenv("ZHIPU_API_BASE") or "https://open.bigmodel.cn/api/paas/v4"
        self.client = OpenAI(api_key=api_key, base_url=base_url)

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
        return self._parse_response(response, tools)
