import os
from typing import Dict, List, Optional, Union

from openai import OpenAI

from mem0.configs.llms.aihubmix import AIHubMixConfig
from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.base import LLMBase
from mem0.llms.openai import OpenAILLM


class AIHubMixLLM(LLMBase):
    def __init__(self, config: Optional[Union[BaseLlmConfig, Dict]] = None):
        if config is None:
            config = AIHubMixConfig()
        elif isinstance(config, dict):
            config = AIHubMixConfig(**config)
        elif not isinstance(config, AIHubMixConfig):
            config = AIHubMixConfig(
                model=config.model,
                temperature=config.temperature,
                api_key=config.api_key,
                max_tokens=config.max_tokens,
                top_p=config.top_p,
                top_k=config.top_k,
                enable_vision=config.enable_vision,
                vision_details=config.vision_details,
                reasoning_effort=config.reasoning_effort,
                http_client_proxies=config.http_client_proxies,
                is_reasoning_model=config.is_reasoning_model,
            )
        super().__init__(config)

        api_key = config.api_key or os.getenv("AIHUBMIX_API_KEY")
        if not api_key:
            raise ValueError("AIHubMix API key is required: set api_key or AIHUBMIX_API_KEY")
        base_url = config.aihubmix_base_url or os.getenv("AIHUBMIX_BASE_URL") or "https://aihubmix.com/v1"
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def generate_response(
        self,
        messages: List[Dict[str, str]],
        response_format=None,
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
        **kwargs,
    ):
        params = self._get_supported_params(messages=messages, **kwargs)
        params.update(model=self.config.model, messages=messages)
        if response_format:
            params["response_format"] = response_format
        if tools:
            params["tools"] = tools
            params["tool_choice"] = tool_choice
        response = self.client.chat.completions.create(**params)
        return OpenAILLM._parse_response(self, response, tools)
