from typing import Dict, List, Optional

from openai import OpenAI

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.base import LLMBase


class LMStudioLLM(LLMBase):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config)

        self.config.model = (
            self.config.model
            or "lmstudio-community/Meta-Llama-3.1-70B-Instruct-GGUF/Meta-Llama-3.1-70B-Instruct-IQ2_M.gguf"
        )
        self.config.api_key = self.config.api_key or "lm-studio"

        self.client = OpenAI(base_url=self.config.lmstudio_base_url, api_key=self.config.api_key)

    def generate_response(
        self,
        messages: List[Dict[str, str]],
        response_format: dict = {"type": "json_object"},
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
    ):
        """
        Generate a response based on the given messages using LM Studio.

        Args:
            messages (list): List of message dicts containing 'role' and 'content'.
            response_format (str or object, optional): Format of the response. Defaults to "text".
            tools (list, optional): List of tools that the model can call. Defaults to None.
            tool_choice (str, optional): Tool choice method. Defaults to "auto".

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
        if self.config.lmstudio_response_format is not None:
            params["response_format"] = self.config.lmstudio_response_format

        response = self.client.chat.completions.create(**params)
        return response.choices[0].message.content
