import os
from typing import Dict, List, Optional

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.base import LLMBase

SCOPE = "https://cognitiveservices.azure.com/.default"


class AzureOpenAIStructuredLLM(LLMBase):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config)

        # Model name should match the custom deployment name chosen for it.
        if not self.config.model:
            self.config.model = "gpt-4o-2024-08-06"

        api_key = self.config.azure_kwargs.api_key or os.getenv("LLM_AZURE_OPENAI_API_KEY")
        azure_deployment = self.config.azure_kwargs.azure_deployment or os.getenv("LLM_AZURE_DEPLOYMENT")
        azure_endpoint = self.config.azure_kwargs.azure_endpoint or os.getenv("LLM_AZURE_ENDPOINT")
        api_version = self.config.azure_kwargs.api_version or os.getenv("LLM_AZURE_API_VERSION")
        default_headers = self.config.azure_kwargs.default_headers

        # If the API key is not provided or is a placeholder, use DefaultAzureCredential.
        if api_key is None or api_key == "" or api_key == "your-api-key":
            self.credential = DefaultAzureCredential()
            azure_ad_token_provider = get_bearer_token_provider(
                self.credential,
                SCOPE,
            )
            api_key = None
        else:
            azure_ad_token_provider = None

        # Can display a warning if API version is of model and api-version
        self.client = AzureOpenAI(
            azure_deployment=azure_deployment,
            azure_endpoint=azure_endpoint,
            azure_ad_token_provider=azure_ad_token_provider,
            api_version=api_version,
            api_key=api_key,
            http_client=self.config.http_client,
            default_headers=default_headers,
        )

    def generate_response(
        self,
        messages: List[Dict[str, str]],
        response_format: Optional[str] = None,
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
    ) -> str:
        """
        Generate a response based on the given messages using Azure OpenAI.

        Args:
            messages (List[Dict[str, str]]): A list of dictionaries, each containing a 'role' and 'content' key.
            response_format (Optional[str]): The desired format of the response. Defaults to None.

        Returns:
            str: The generated response.
        """

        user_prompt = messages[-1]["content"]

        user_prompt = user_prompt.replace("assistant", "ai")

        messages[-1]["content"] = user_prompt

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

        if tools:
            params["tools"] = tools
            params["tool_choice"] = tool_choice

        response = self.client.chat.completions.create(**params)
        return self._parse_response(response, tools)
