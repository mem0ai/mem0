import os
from typing import Dict, List, Optional

from openai import OpenAI

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.base import LLMBase


class OpenAIStructuredLLM(LLMBase):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config)

        if not self.config.model:
            self.config.model = "gpt-5-mini"

        api_key = self.config.api_key or os.getenv("OPENAI_API_KEY")
        base_url = self.config.openai_base_url or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1"

        # This provider is mapped to OpenAIConfig in the LLM factory, so it accepts
        # `extra_headers` too; honour it here rather than silently ignoring it.
        # getattr keeps a plain BaseLlmConfig (the annotated type) working.
        client_kwargs = {}
        extra_headers = getattr(self.config, "extra_headers", None)
        if extra_headers:
            client_kwargs["default_headers"] = extra_headers

        self.client = OpenAI(api_key=api_key, base_url=base_url, **client_kwargs)

    def generate_response(
        self,
        messages: List[Dict[str, str]],
        response_format: Optional[str] = None,
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
    ) -> str:
        """
        Generate a response based on the given messages using OpenAI.

        Args:
            messages (List[Dict[str, str]]): A list of dictionaries, each containing a 'role' and 'content' key.
            response_format (Optional[str]): The desired format of the response. Defaults to None.


        Returns:
            str: The generated response.
        """
        params = self._get_supported_params(messages=messages)
        params["model"] = self.config.model

        if response_format:
            params["response_format"] = response_format
        if tools:
            params["tools"] = tools
            params["tool_choice"] = tool_choice

        response = self.client.beta.chat.completions.parse(**params)
        return response.choices[0].message.content
