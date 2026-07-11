import json
import logging
import os
from contextvars import ContextVar
from typing import Any, Dict, List, Optional, Union

from openai import OpenAI

from mem0.configs.llms.base import BaseLlmConfig
from mem0.configs.llms.openai import OpenAIConfig
from mem0.llms.base import LLMBase
from mem0.memory.utils import extract_json


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
            )

        super().__init__(config)
        self._last_usage_var: ContextVar[Optional[Dict[str, Any]]] = ContextVar(
            f"openai_last_usage_{id(self)}",
            default=None,
        )
        self._capture_usage_var: ContextVar[bool] = ContextVar(
            f"openai_capture_usage_{id(self)}",
            default=False,
        )

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

    def _extract_usage(self, response) -> Optional[Dict[str, Any]]:
        usage = getattr(response, "usage", None)
        if usage is None:
            return None

        if hasattr(usage, "model_dump"):
            usage_dict = usage.model_dump()
        elif isinstance(usage, dict):
            usage_dict = usage
        elif hasattr(usage, "__dict__"):
            usage_dict = {
                key: value for key, value in vars(usage).items()
                if not key.startswith("_")
            }
        else:
            return None

        return usage_dict or None

    def reset_last_usage(self) -> None:
        self._last_usage_var.set(None)

    def get_last_usage(self) -> Optional[Dict[str, Any]]:
        usage = self._last_usage_var.get()
        if usage is None:
            return None
        return dict(usage)

    def start_usage_capture(self) -> None:
        self.reset_last_usage()
        self._capture_usage_var.set(True)

    def stop_usage_capture(self) -> None:
        self._capture_usage_var.set(False)

    def _merge_usage_values(self, current, incoming):
        if isinstance(current, dict) and isinstance(incoming, dict):
            merged = dict(current)
            for key, value in incoming.items():
                merged[key] = self._merge_usage_values(merged[key], value) if key in merged else value
            return merged

        if (
            isinstance(current, (int, float))
            and not isinstance(current, bool)
            and isinstance(incoming, (int, float))
            and not isinstance(incoming, bool)
        ):
            return current + incoming

        return incoming

    def _store_usage(self, usage: Optional[Dict[str, Any]]) -> None:
        if not self._capture_usage_var.get():
            self._last_usage_var.set(usage)
            return

        if usage:
            current_usage = self._last_usage_var.get() or {}
            self._last_usage_var.set(self._merge_usage_values(current_usage, usage))

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
        if not self._capture_usage_var.get():
            self.reset_last_usage()
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
        response = self.client.chat.completions.create(**params)
        self._store_usage(self._extract_usage(response))
        parsed_response = self._parse_response(response, tools)
        if self.config.response_callback:
            try:
                self.config.response_callback(self, response, params)
            except Exception as e:
                # Log error but don't propagate
                logging.error(f"Error due to callback: {e}")
                pass
        return parsed_response
