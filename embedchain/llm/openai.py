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

    def get_llm_model_answer(self, prompt) -> str:
        response = self._get_answer(prompt, self.config)
        return response

    def _get_answer(self, prompt: str, config: BaseLlmConfig) -> str:
        messages = []
        if config.system_prompt:
            messages.append(SystemMessage(content=config.system_prompt))
        messages.append(HumanMessage(content=prompt))
        kwargs = {
            "model": config.model or "gpt-3.5-turbo",
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "model_kwargs": {},
        }
        api_key = config.api_key or os.environ["OPENAI_API_KEY"]
        base_url = config.base_url or os.environ.get("OPENAI_API_BASE", None)
        if config.top_p:
            kwargs["model_kwargs"]["top_p"] = config.top_p
        if config.stream:
            callbacks = config.callbacks if config.callbacks else [StreamingStdOutCallbackHandler()]
            chat = ChatOpenAI(
                **kwargs,
                streaming=config.stream,
                callbacks=callbacks,
                api_key=api_key,
                base_url=base_url,
            )
        else:
            chat = ChatOpenAI(**kwargs, api_key=api_key, base_url=base_url)
        if self.tools:
            return self._query_function_call(chat, self.tools, messages)

        return chat.invoke(messages).content

    def _query_function_call(
        self,
        chat: ChatOpenAI,
        tools: Optional[Union[Dict[str, Any], Type[BaseModel], Callable[..., Any], BaseTool]],
        messages: list[BaseMessage],
    ) -> str:
        from langchain.output_parsers.openai_tools import JsonOutputToolsParser
        from langchain_core.utils.function_calling import \
            convert_to_openai_tool

        openai_tools = [convert_to_openai_tool(tools)]
        chat = chat.bind(tools=openai_tools).pipe(JsonOutputToolsParser())
        try:
            return json.dumps(chat.invoke(messages)[0])
        except IndexError:
            return "Input could not be mapped to the function!"
