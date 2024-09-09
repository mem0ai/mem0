import json
import os
from typing import Any, Callable, Dict, Optional, Type, Union

from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.schema import BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from embedchain.config import BaseLlmConfig
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.llm.base import BaseLlm


@register_deserializable
class OpenAILlm(BaseLlm):
    def __init__(
        self,
        config: Optional[BaseLlmConfig] = None,
        tools: Optional[Union[Dict[str, Any], Type[BaseModel], Callable[..., Any], BaseTool]] = None,
    ):
        self.tools = tools
        super().__init__(config=config)

    def get_llm_model_answer(self, prompt) -> tuple[str, Optional[dict[str, Any]]]:
        if self.config.token_usage:
            response, token_info = self._get_answer(prompt, self.config)
            model_name = "openai/" + self.config.model
            if model_name not in self.config.model_pricing_map:
                raise ValueError(
                    f"Model {model_name} not found in `model_prices_and_context_window.json`. \
                    You can disable token usage by setting `token_usage` to False."
                )
            total_cost = (
                self.config.model_pricing_map[model_name]["input_cost_per_token"] * token_info["prompt_tokens"]
            ) + self.config.model_pricing_map[model_name]["output_cost_per_token"] * token_info["completion_tokens"]
            response_token_info = {
                "prompt_tokens": token_info["prompt_tokens"],
                "completion_tokens": token_info["completion_tokens"],
                "total_tokens": token_info["prompt_tokens"] + token_info["completion_tokens"],
                "total_cost": round(total_cost, 10),
                "cost_currency": "USD",
            }
            return response, response_token_info

        return self._get_answer(prompt, self.config)

    def _get_answer(self, prompt: str, config: BaseLlmConfig) -> str:
        messages = []
        if config.system_prompt:
            messages.append(SystemMessage(content=config.system_prompt))
        messages.append(HumanMessage(content=prompt))
        kwargs = {
            "model": config.model or "gpt-4o-mini",
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "model_kwargs": config.model_kwargs or {},
        }
        api_key = config.api_key or os.environ["OPENAI_API_KEY"]
        base_url = config.base_url or os.environ.get("OPENAI_API_BASE", None)
        if config.top_p:
            kwargs["top_p"] = config.top_p
        if config.default_headers:
            kwargs["default_headers"] = config.default_headers
        if config.stream:
            callbacks = config.callbacks if config.callbacks else [StreamingStdOutCallbackHandler()]
            chat = ChatOpenAI(
                **kwargs,
                streaming=config.stream,
                callbacks=callbacks,
                api_key=api_key,
                base_url=base_url,
                http_client=config.http_client,
                http_async_client=config.http_async_client,
            )
        else:
            chat = ChatOpenAI(
                **kwargs,
                api_key=api_key,
                base_url=base_url,
                http_client=config.http_client,
                http_async_client=config.http_async_client,
            )
        if self.tools:
            return self._query_function_call(chat, self.tools, messages)

        chat_response = chat.invoke(messages)
        if self.config.token_usage:
            return chat_response.content, chat_response.response_metadata["token_usage"]
        return chat_response.content

    def _query_function_call(
        self,
        chat: ChatOpenAI,
        tools: Optional[Union[Dict[str, Any], Type[BaseModel], Callable[..., Any], BaseTool]],
        messages: list[BaseMessage],
    ) -> str:
        from langchain.output_parsers.openai_tools import JsonOutputToolsParser
        from langchain_core.utils.function_calling import convert_to_openai_tool

        openai_tools = [convert_to_openai_tool(tools)]
        chat = chat.bind(tools=openai_tools).pipe(JsonOutputToolsParser())
        try:
            return json.dumps(chat.invoke(messages)[0])
        except IndexError:
            return "Input could not be mapped to the function!"
