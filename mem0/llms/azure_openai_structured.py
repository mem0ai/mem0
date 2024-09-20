import json
import os
from typing import Dict, List, Optional

from openai import AzureOpenAI

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.base import LLMBase


class AzureOpenAIStructuredLLM(LLMBase):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config)

        # Model name should match the custom deployment name chosen for it.
        if not self.config.model:
            self.config.model = "gpt-4o-2024-08-06"

        api_key = os.getenv("LLM_AZURE_OPENAI_API_KEY") or self.config.azure_kwargs.api_key
        azure_deployment = os.getenv("LLM_AZURE_DEPLOYMENT") or self.config.azure_kwargs.azure_deployment
        azure_endpoint = os.getenv("LLM_AZURE_ENDPOINT") or self.config.azure_kwargs.azure_endpoint
        api_version = os.getenv("LLM_AZURE_API_VERSION") or self.config.azure_kwargs.api_version
        # Can display a warning if API version is of model and api-version

        self.client = AzureOpenAI(
            azure_deployment=azure_deployment,
            azure_endpoint=azure_endpoint,
            api_version=api_version,
            api_key=api_key,
            http_client=self.config.http_client,
        )

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
        tool_choice: str = "auto",
    ):
        """
        Generate a response based on the given messages using Azure OpenAI.

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
        if tools:
            params["tools"] = tools
            params["tool_choice"] = tool_choice

        response = self.client.chat.completions.create(**params)
        return self._parse_response(response, tools)
