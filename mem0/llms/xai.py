import os
from typing import Dict, List, Optional

from openai import OpenAI

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.base import LLMBase


class XAILLM(LLMBase):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config)

        if not self.config.model:
            self.config.model = "grok-2-latest"

        api_key = self.config.api_key or os.getenv("XAI_API_KEY")
        base_url = self.config.xai_base_url or os.getenv("XAI_API_BASE") or "https://api.x.ai/v1"
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def generate_response(self, messages: List[Dict[str, str]], response_format=None):
        """
        Generate a response based on the given messages using XAI.

        Args:
            messages (list): List of message dicts containing 'role' and 'content'.
            response_format (str or object, optional): Format of the response. Defaults to "text".

        Returns:
            str: The generated response.
        """
        params = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "top_p": self.config.top_p,
        }

        if response_format:
            params["response_format"] = response_format

        response = self.client.chat.completions.create(**params)
        return response.choices[0].message.content
