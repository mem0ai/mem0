import json
import os
from typing import Dict, List, Optional, Union

from openai import AzureOpenAI

from mem0.configs.llms.azure import AzureOpenAIConfig
from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.base import LLMBase
from mem0.memory.utils import extract_json


class AzureOpenAILLM(LLMBase):
    def __init__(self, config: Optional[Union[BaseLlmConfig, AzureOpenAIConfig, Dict]] = None):
        # Convert to AzureOpenAIConfig if needed
        if config is None:
            config = AzureOpenAIConfig()
        elif isinstance(config, dict):
            config = AzureOpenAIConfig(**config)
        elif isinstance(config, BaseLlmConfig) and not isinstance(config, AzureOpenAIConfig):
            # Convert BaseLlmConfig to AzureOpenAIConfig
            config = AzureOpenAIConfig(
                model=config.model,
                temperature=config.temperature,
                api_key=config.api_key,
                max_tokens=config.max_tokens,
                top_p=config.top_p,
                top_k=config.top_k,
                enable_vision=config.enable_vision,
                vision_details=config.vision_details,
                http_client_proxies=config.http_client,
            )

        super().__init__(config)

        # Model name should match the custom deployment name chosen for it.
        if not self.config.model:
            self.config.model = "gpt-4o"

        api_key = self.config.azure_kwargs.api_key or os.getenv("LLM_AZURE_OPENAI_API_KEY")
        azure_deployment = self.config.azure_kwargs.azure_deployment or os.getenv("LLM_AZURE_DEPLOYMENT")
        azure_endpoint = self.config.azure_kwargs.azure_endpoint or os.getenv("LLM_AZURE_ENDPOINT")
        api_version = self.config.azure_kwargs.api_version or os.getenv("LLM_AZURE_API_VERSION")
        default_headers = self.config.azure_kwargs.default_headers

        self.client = AzureOpenAI(
            azure_deployment=azure_deployment,
            azure_endpoint=azure_endpoint,
            api_version=api_version,
            api_key=api_key,
            http_client=self.config.http_client,
            default_headers=default_headers,
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
        """
        Generate a response based on the given messages using Azure OpenAI.

        Args:
            messages (list): List of message dicts containing 'role' and 'content'.
            response_format (str or object, optional): Format of the response. Defaults to "text".
            tools (list, optional): List of tools that the model can call. Defaults to None.
            tool_choice (str, optional): Tool choice method. Defaults to "auto".
            **kwargs: Additional Azure OpenAI-specific parameters.

        Returns:
            str: The generated response.
        """

        user_prompt = messages[-1]["content"]

        user_prompt = user_prompt.replace("assistant", "ai")

        messages[-1]["content"] = user_prompt

        params = self._get_supported_params(messages=messages, **kwargs)
        
        # Add model and messages
        params.update({
            "model": self.config.model,
            "messages": messages,
        })

        if tools:
            params["tools"] = tools
            params["tool_choice"] = tool_choice

        response = self.client.chat.completions.create(**params)
        return self._parse_response(response, tools)
