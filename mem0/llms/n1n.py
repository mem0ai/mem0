import json
import os
from typing import Dict, List, Optional, Union

from openai import OpenAI

from mem0.configs.llms.base import BaseLlmConfig
from mem0.configs.llms.n1n import N1NConfig
from mem0.llms.base import LLMBase
from mem0.memory.utils import extract_json


class N1NLLM(LLMBase):
    """
    N1N LLM provider implementation.
    
    N1N API provides access to 400+ large language models through an OpenAI-compatible API.
    This includes models from OpenAI, Anthropic, Google, Meta, and many more providers.
    
    Features:
    - Single API key for all 400+ models
    - OpenAI-compatible endpoints
    - Competitive pricing (up to 1/10 of official prices)
    - No VPN required, global access
    - Multimodal capabilities (text, image, video, audio)
    
    For more information:
    - Website: https://n1n.ai/
    - Documentation: https://docs.n1n.ai/
    - Get API Key: https://n1n.ai/console
    """

    def __init__(self, config: Optional[Union[BaseLlmConfig, N1NConfig, Dict]] = None):
        """
        Initialize N1N LLM client.
        
        Args:
            config: Configuration object (N1NConfig, BaseLlmConfig, or dict)
        """
        # Convert to N1NConfig if needed
        if config is None:
            config = N1NConfig()
        elif isinstance(config, dict):
            config = N1NConfig(**config)
        elif isinstance(config, BaseLlmConfig) and not isinstance(config, N1NConfig):
            # Convert BaseLlmConfig to N1NConfig
            config = N1NConfig(
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

        # Set default model if not specified
        self.config.model = self.config.model or "gpt-4o-mini"

        # Get API key from config or environment
        api_key = self.config.api_key or os.getenv("N1N_API_KEY")
        if not api_key:
            raise ValueError(
                "N1N API key is required. Set it in config or as N1N_API_KEY environment variable. "
                "Get your API key from https://n1n.ai/console"
            )

        # Initialize OpenAI client with n1n base URL
        self.client = OpenAI(
            base_url=self.config.n1n_base_url,
            api_key=api_key,
            http_client=self.config.http_client,
        )

    def _parse_response(self, response, tools):
        """
        Process the response based on whether tools are used or not.

        Args:
            response: The raw response from n1n API.
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
        Generate a response based on the given messages using n1n API.

        Args:
            messages (list): List of message dicts containing 'role' and 'content'.
            response_format (str or object, optional): Format of the response. Defaults to None.
            tools (list, optional): List of tools that the model can call. Defaults to None.
            tool_choice (str, optional): Tool choice method. Defaults to "auto".
            **kwargs: Additional n1n-specific parameters.

        Returns:
            str or dict: The generated response.
        """
        # Use the base class method to get supported params based on model type
        params = self._get_supported_params(messages=messages, **kwargs)
        
        # Update with required parameters
        params.update(
            {
                "model": self.config.model,
                "messages": messages,
            }
        )

        # Add optional parameters
        if response_format:
            params["response_format"] = response_format
        if tools:
            params["tools"] = tools
            params["tool_choice"] = tool_choice

        # Add n1n-specific response format if configured
        if hasattr(self.config, "n1n_response_format") and self.config.n1n_response_format:
            params["response_format"] = self.config.n1n_response_format

        # Make API call
        response = self.client.chat.completions.create(**params)
        return self._parse_response(response, tools)
