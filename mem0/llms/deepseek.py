import json
import os
from typing import Dict, List, Optional

from openai import OpenAI

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.base import LLMBase


class DeepSeekLLM(LLMBase):
    """
    A class for interacting with DeepSeek's language models using the specified configuration.
    """

    def __init__(self, config: Optional[BaseLlmConfig] = None):
        """
        Initializes the DeepSeekLLM instance with the given configuration.

        Args:
            config (Optional[BaseLlmConfig]): Configuration settings for the language model.
        """
        super().__init__(config)

        if not self.config.model:
            self.config.model = "deepseek-chat"

        api_key = self.config.api_key or os.getenv("DEEPSEEK_API_KEY")
        base_url = (
            self.config.deepseek_base_url
            or os.getenv("DEEPSEEK_API_BASE")
            or "https://api.deepseek.com"
        )
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def generate_response(
        self,
        messages: List[Dict[str, str]],
    ) -> str:
        """
        Generates a response using DeepSeek based on the provided messages.

        Args:
            messages (List[Dict[str, str]]): A list of dictionaries, each containing a 'role' and 'content' key.

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
        response = self.client.chat.completions.create(**params)
        return response.choices[0].message.content
