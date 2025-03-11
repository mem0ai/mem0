import json
import os
from typing import Dict, List, Optional

from openai import AzureOpenAI

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.base import LLMBase


class AzureOpenAIStructuredLLM(LLMBase):
    """
    A class for interacting with Azure OpenAI models using the specified configuration.
    """

    def __init__(self, config: Optional[BaseLlmConfig] = None):
        """
        Initializes the AzureOpenAIStructuredLLM instance with the given configuration.

        Args:
            config (Optional[BaseLlmConfig]): Configuration settings for the language model.
        """
        super().__init__(config)

        # Ensure model name is set; it should match the Azure OpenAI deployment name.
        if not self.config.model:
            self.config.model = "gpt-4o-2024-08-06"

        api_key = (
            os.getenv("LLM_AZURE_OPENAI_API_KEY") or self.config.azure_kwargs.api_key
        )
        azure_deployment = (
            os.getenv("LLM_AZURE_DEPLOYMENT")
            or self.config.azure_kwargs.azure_deployment
        )
        azure_endpoint = (
            os.getenv("LLM_AZURE_ENDPOINT") or self.config.azure_kwargs.azure_endpoint
        )
        api_version = (
            os.getenv("LLM_AZURE_API_VERSION") or self.config.azure_kwargs.api_version
        )
        default_headers = self.config.azure_kwargs.default_headers

        self.client = AzureOpenAI(
            azure_deployment=azure_deployment,
            azure_endpoint=azure_endpoint,
            api_version=api_version,
            api_key=api_key,
            http_client=self.config.http_client,
            default_headers=default_headers,
        )

    def generate_response(
        self,
        messages: List[Dict[str, str]],
        response_format: Optional[str] = None,
    ) -> str:
        """
        Generates a response using Azure OpenAI based on the provided messages.

        Args:
            messages (List[Dict[str, str]]): A list of dictionaries, each containing a 'role' and 'content' key.
            response_format (Optional[str]): The desired format of the response. Defaults to None.

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

        if response_format:
            params["response_format"] = response_format

        response = self.client.chat.completions.create(**params)
        return response.choices[0].message.content
