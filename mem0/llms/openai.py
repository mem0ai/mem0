import copy
import json
import logging
import os
from typing import Dict, List, Optional, Union

from openai import OpenAI

from mem0.configs.llms.base import BaseLlmConfig
from mem0.configs.llms.openai import OpenAIConfig
from mem0.llms.base import LLMBase
from mem0.memory.utils import extract_json


class OpenAILLM(LLMBase):
    # Subclasses may bypass this class's `__init__` and call `LLMBase.__init__`
    # directly (see integrations/hermes-plugin-mem0), so the flag `generate_response`
    # reads has to exist before it is assigned.
    _uses_openrouter = False

    def __init__(self, config: Optional[Union[BaseLlmConfig, OpenAIConfig, Dict]] = None):
        # Convert to OpenAIConfig if needed
        if config is None:
            config = OpenAIConfig()
        elif isinstance(config, dict):
            config = OpenAIConfig(**config)
        elif isinstance(config, BaseLlmConfig) and not isinstance(config, OpenAIConfig):
            # Convert BaseLlmConfig to OpenAIConfig
            config = OpenAIConfig(
                model=config.model,
                temperature=config.temperature,
                api_key=config.api_key,
                max_tokens=config.max_tokens,
                top_p=config.top_p,
                top_k=config.top_k,
                enable_vision=config.enable_vision,
                vision_details=config.vision_details,
                reasoning_effort=getattr(config, 'reasoning_effort', None),
                http_client_proxies=config.http_client_proxies,
                is_reasoning_model=getattr(config, 'is_reasoning_model', None),
            )

        super().__init__(config)

        uses_openrouter = bool(os.environ.get("OPENROUTER_API_KEY"))
        # Remember the choice: the client below and the OpenRouter-only request
        # fields in `generate_response` must agree, and the environment can
        # change between construction and the first call.
        self._uses_openrouter = uses_openrouter

        # When OpenRouter fallback routing is configured, `models` is the ordered
        # candidate list and its first entry is what the request asks for. Resolve
        # it here rather than at request time so that reasoning-model
        # classification and parameter filtering (both keyed on `config.model`)
        # see the same model the request will actually carry. An explicitly
        # configured `model` still wins, which matches OpenRouter's own
        # semantics: `model` is the primary and `models` the fallbacks.
        # Copy before assigning — `LLMBase` keeps the caller's config object, and
        # a config reused for a second client under a different provider must not
        # inherit the OpenRouter primary.
        if uses_openrouter and self.config.models and not self.config.model:
            self.config = copy.copy(self.config)
            self.config.model = self.config.models[0]

        if not self.config.model:
            self.config.model = "gpt-5-mini"

        if uses_openrouter:  # Use OpenRouter
            self.client = OpenAI(
                api_key=os.environ.get("OPENROUTER_API_KEY"),
                base_url=self.config.openrouter_base_url
                or os.getenv("OPENROUTER_API_BASE")
                or "https://openrouter.ai/api/v1",
            )
        else:
            api_key = self.config.api_key or os.getenv("OPENAI_API_KEY")
            base_url = self.config.openai_base_url or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1"

            self.client = OpenAI(api_key=api_key, base_url=base_url)

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
        Generate a JSON response based on the given messages using OpenAI.

        Args:
            messages (list): List of message dicts containing 'role' and 'content'.
            response_format (str or object, optional): Format of the response. Defaults to "text".
            tools (list, optional): List of tools that the model can call. Defaults to None.
            tool_choice (str, optional): Tool choice method. Defaults to "auto".
            **kwargs: Additional OpenAI-specific parameters.

        Returns:
            json: The generated response.
        """
        params = self._get_supported_params(messages=messages, **kwargs)
        
        params.update({
            "model": self.config.model,
            "messages": messages,
        })

        if self._uses_openrouter:
            openrouter_extra_body = {}
            if self.config.models:
                # `models` and `route` are OpenRouter-only fields: the OpenAI SDK
                # has no such parameters, so they have to travel in `extra_body`
                # or the call fails before a request is built. OpenRouter tries
                # `model` first and then the array in order, so with only `models`
                # configured `model` is its first entry, and with an explicit
                # `model` the array is the fallback chain behind it.
                # https://openrouter.ai/docs/guides/routing/model-fallbacks
                openrouter_extra_body["models"] = self.config.models
                if self.config.route:
                    openrouter_extra_body["route"] = self.config.route

            openrouter_extra_headers = {}
            if self.config.site_url and self.config.app_name:
                openrouter_extra_headers = {
                    "HTTP-Referer": self.config.site_url,
                    "X-Title": self.config.app_name,
                }

            # Read the caller's own `extra_body` / `extra_headers` from `kwargs`
            # rather than from `params`: for reasoning models `_get_supported_params`
            # rebuilds `params` from scratch without copying `**kwargs`, so a value
            # read back out of `params` is missing on that path. Note this only
            # covers the OpenRouter branch; on the plain OpenAI path the same
            # drop still happens inside `LLMBase._get_supported_params`.
            caller_extra_body = kwargs.get("extra_body") or {}
            if caller_extra_body or openrouter_extra_body:
                params["extra_body"] = {**caller_extra_body, **openrouter_extra_body}

            caller_extra_headers = kwargs.get("extra_headers") or {}
            if caller_extra_headers or openrouter_extra_headers:
                params["extra_headers"] = {**caller_extra_headers, **openrouter_extra_headers}

        else:
            # Only send OpenAI-specific parameters when the user has explicitly
            # configured them. OpenAI-compatible backends (Gemini, Groq, vLLM, etc.)
            # reject unknown fields, so `store` must be opt-in, not opt-out.
            if self.config.store is not None:
                params["store"] = self.config.store

        if response_format:
            params["response_format"] = response_format
        if tools:  # TODO: Remove tools if no issues found with new memory addition logic
            params["tools"] = tools
            params["tool_choice"] = tool_choice
        response = self.client.chat.completions.create(**params)
        parsed_response = self._parse_response(response, tools)
        if self.config.response_callback:
            try:
                self.config.response_callback(self, response, params)
            except Exception as e:
                # Log error but don't propagate
                logging.error(f"Error due to callback: {e}")
                pass
        return parsed_response
