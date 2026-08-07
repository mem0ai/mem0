import email.utils
import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Union

import openai
from openai import OpenAI

from mem0.configs.llms.base import BaseLlmConfig
from mem0.configs.llms.openai import OpenAIConfig
from mem0.exceptions import LLMError, NetworkError, RateLimitError
from mem0.llms.base import LLMBase
from mem0.memory.utils import extract_json

_OPENAI_RETRYABLE_ERRORS = (
    openai.RateLimitError,
    openai.APIConnectionError,  # base class of APITimeoutError
    openai.InternalServerError,
)


def _openai_retry_after(exc):
    """Server-directed Retry-After (seconds) from an OpenAI error, or None if absent/unparseable.

    Mirrors the OpenAI SDK precedence: ``retry-after-ms`` (milliseconds) first, then
    ``retry-after`` as either numeric seconds or an HTTP-date. A None/unparseable result
    makes the caller fall back to computed backoff; the retry layer also ignores
    negative/non-finite values, so a past HTTP-date is safe.
    """
    response = getattr(exc, "response", None)
    if response is None:
        return None
    headers = response.headers

    ms = headers.get("retry-after-ms")
    if ms:
        try:
            return float(ms) / 1000.0
        except (TypeError, ValueError):
            pass

    value = headers.get("retry-after")
    if value:
        try:
            return float(value)
        except (TypeError, ValueError):
            pass
        try:
            retry_dt = email.utils.parsedate_to_datetime(value)
        except (TypeError, ValueError):
            retry_dt = None
        if retry_dt is not None:
            if retry_dt.tzinfo is None:
                retry_dt = retry_dt.replace(tzinfo=timezone.utc)
            return (retry_dt - datetime.now(timezone.utc)).total_seconds()
    return None


def _to_mem0_llm_error(exc):
    """Translate an exhausted OpenAI transient error into a mem0 typed exception."""
    if isinstance(exc, openai.RateLimitError):
        return RateLimitError(message=str(exc), error_code="LLM_RATE_LIMIT", debug_info={"provider": "openai"})
    if isinstance(exc, (openai.APITimeoutError, openai.APIConnectionError)):
        return NetworkError(message=str(exc), error_code="LLM_NETWORK", debug_info={"provider": "openai"})
    return LLMError(message=str(exc), debug_info={"provider": "openai"})


class OpenAILLM(LLMBase):
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
                max_retries=getattr(config, 'max_retries', 0),
            )

        super().__init__(config)

        if not self.config.model:
            self.config.model = "gpt-5-mini"

        if os.environ.get("OPENROUTER_API_KEY"):  # Use OpenRouter
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

        if os.getenv("OPENROUTER_API_KEY"):
            openrouter_params = {}
            if self.config.models:
                openrouter_params["models"] = self.config.models
                openrouter_params["route"] = self.config.route
                params.pop("model")

            if self.config.site_url and self.config.app_name:
                extra_headers = {
                    "HTTP-Referer": self.config.site_url,
                    "X-Title": self.config.app_name,
                }
                openrouter_params["extra_headers"] = extra_headers

            params.update(**openrouter_params)
        
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
        response = self._retry(
            lambda: self.client.chat.completions.create(**params),
            retry_on=_OPENAI_RETRYABLE_ERRORS,
            on_giveup=_to_mem0_llm_error,
            retry_after=_openai_retry_after,
        )
        parsed_response = self._parse_response(response, tools)
        if self.config.response_callback:
            try:
                self.config.response_callback(self, response, params)
            except Exception as e:
                # Log error but don't propagate
                logging.error(f"Error due to callback: {e}")
                pass
        return parsed_response
