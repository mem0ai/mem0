import json
import logging
import os
from typing import Dict, List, Optional, Union

from openai import OpenAI

from mem0.configs.llms.base import BaseLlmConfig
from mem0.configs.llms.lm_studio import LMStudioConfig
from mem0.llms.base import LLMBase
from mem0.memory.utils import extract_json


class LMStudioLLM(LLMBase):
    def __init__(self, config: Optional[Union[BaseLlmConfig, LMStudioConfig, Dict]] = None):
        if config is None:
            config = LMStudioConfig()
        elif isinstance(config, dict):
            config = LMStudioConfig(**config)
        elif isinstance(config, BaseLlmConfig) and not isinstance(config, LMStudioConfig):
            config = LMStudioConfig(
                model=config.model,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                top_p=config.top_p,
            )

        super().__init__(config)

        self.client = OpenAI(base_url=self.config.base_url, api_key=self.config.api_key)

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
        params = self._get_supported_params(**kwargs)
        
        params.update({
            "model": self.config.model,
            "messages": messages,
            "stream": False,
        })

        if response_format:
            params["response_format"] = response_format
        if tools:
            params["tools"] = tools
            params["tool_choice"] = tool_choice

        response = self.client.chat.completions.create(**params)
        parsed_response = self._parse_response(response, tools)
        return parsed_response
