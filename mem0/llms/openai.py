import json
import logging
import os
from typing import Dict, List, Optional, Union

from openai import OpenAI

from mem0.configs.llms.base import BaseLlmConfig
from mem0.configs.llms.openai import OpenAIConfig
from mem0.llms.base import LLMBase
from mem0.memory.utils import extract_json


def _content_from_sse_chat_completion(response: str) -> Optional[str]:
    """Extract concatenated delta content from SSE chat-completion text.

    Some OpenAI-compatible routers proxy streamed chat completions as raw
    ``data: {...}`` text even for callers using the non-streaming SDK path. In
    that case the OpenAI SDK may hand us a plain string instead of an object
    with ``choices``. Return ``None`` when the string is not recognizably an SSE
    chat-completions payload so the caller can keep normal error behaviour.
    """
    if not response.lstrip().startswith("data:"):
        return None

    content_parts: list[str] = []
    saw_chat_chunk = False
    for raw_line in response.splitlines():
        line = raw_line.strip()
        if not line.startswith("data:"):
            continue
        data = line[len("data:"):].strip()
        if not data or data == "[DONE]":
            continue
        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            continue
        if not isinstance(chunk, dict):
            continue
        choices = chunk.get("choices") or []
        if choices:
            saw_chat_chunk = True
        for choice in choices:
            delta = choice.get("delta") or {}
            delta_content = delta.get("content")
            if delta_content is not None:
                content_parts.append(delta_content)
            # Be tolerant of providers that emit a full message shape in a
            # ``data:`` frame instead of a delta chunk.
            message = choice.get("message") or {}
            message_content = message.get("content")
            if message_content is not None:
                content_parts.append(message_content)

    if not saw_chat_chunk:
        return None
    return "".join(content_parts)


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
        if isinstance(response, str):
            content = _content_from_sse_chat_completion(response)
            if content is not None:
                if tools:
                    return {"content": content, "tool_calls": []}
                return content
            raise ValueError("Unsupported string response from OpenAI-compatible backend")

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
