import os
from openai import APIError, OpenAI
from typing import Dict, List, Optional

from mem0.configs.llms.base import BaseLlmConfig
from mem0.configs.llms.siliconflow import SiliconflowConfig
from mem0.openai_error_codes import OpenAPIErrorCode
from mem0.llms.base import LLMBase


class SiliconflowLLM(LLMBase):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        # Convert to SiliconflowConfig if needed
        if config is None:
            config = SiliconflowConfig()
        elif isinstance(config, dict):
            config = SiliconflowConfig(**config)
        elif isinstance(config, BaseLlmConfig) and not isinstance(config, SiliconflowConfig):
            # Convert BaseLlmConfig to SiliconflowConfig
            config = SiliconflowConfig(
                model=config.model,
                temperature=config.temperature,
                api_key=config.api_key,
                max_tokens=config.max_tokens,
                top_p=config.top_p,
                top_k=config.top_k,
            )

        super().__init__(config)

        if not self.config.model:
            self.config.model = "tencent/Hunyuan-MT-7B"

        api_key = self.config.api_key or os.getenv("SILICONFLOW_API_KEY")
        base_url = (
            self.config.siliconflow_base_url
            or os.getenv("SILICONFLOW_BASE_URL")
            or "https://api.siliconflow.com/v1"
        )

        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def _extract_json_content(self, response):
        """
        Extracts JSON content from a response.

        Args:
            response: The response from the API.

        Returns:
            The extracted JSON content.
        """
        from mem0.memory.utils import extract_json
        import json

        if response.choices[0].message.tool_calls:
            tool_calls = response.choices[0].message.tool_calls
            return [
                {
                    "name": tool_call.function.name,
                    "arguments": json.loads(extract_json(tool_call.function.arguments)),
                }
                for tool_call in tool_calls
            ]
        return None

    def _parse_response(self, response, tools):
        """
        Process the response based on whether tools are used or not.

        Args:
            response: The raw response from API.
            tools: The list of tools provided in the request.

        Returns:
            Extracted text content from the response.
        """
        if tools:
            # When tools are used, extract JSON content
            return self._extract_json_content(response)
        else:
            # Directly return the message content
            return response.choices[0].message.content

    def generate_response(self, messages: List[Dict], tools: Optional[List] = None) -> str:
        """
        Generate a response from the LLM based on input messages.

        Args:
            messages (List[Dict]): List of message dicts with 'role' and 'content'.
            tools (Optional[List]): List of tools to be used (if any).
        Returns:
            str: The generated response content.
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

        try:
            response = self.client.chat.completions.create(**params)
            return self._parse_response(response, tools)
        except APIError as e:
            error_code = getattr(e, 'code', None)
            if error_code == OpenAPIErrorCode.FUNCTION_CALL_NOT_SUPPORTED.value:
                # Retry without tools
                params.pop("tools", None)
                response = self.client.chat.completions.create(**params)
                return self._parse_response(response, None)
            else:
                raise e
    

    



