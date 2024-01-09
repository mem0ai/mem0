import json
import os
from typing import Any, Optional

from langchain.chat_models import ChatOpenAI
from langchain.schema import AIMessage, HumanMessage, SystemMessage

from embedchain.config import BaseLlmConfig
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.llm.base import BaseLlm


@register_deserializable
class OpenAILlm(BaseLlm):
    def __init__(self, config: Optional[BaseLlmConfig] = None, functions: Optional[dict[str, Any]] = None):
        self.functions = functions
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
        if config.top_p:
            kwargs["model_kwargs"]["top_p"] = config.top_p
        if config.stream:
            from langchain.callbacks.streaming_stdout import \
                StreamingStdOutCallbackHandler

            callbacks = config.callbacks if config.callbacks else [StreamingStdOutCallbackHandler()]
            chat = ChatOpenAI(**kwargs, streaming=config.stream, callbacks=callbacks, api_key=api_key)
        else:
            chat = ChatOpenAI(**kwargs, api_key=api_key)

        if self.functions is not None:
            from langchain.chains.openai_functions import \
                create_openai_fn_runnable
            from langchain.prompts import ChatPromptTemplate

            structured_prompt = ChatPromptTemplate.from_messages(messages)
            runnable = create_openai_fn_runnable(functions=self.functions, prompt=structured_prompt, llm=chat)
            fn_res = runnable.invoke(
                {
                    "input": prompt,
                }
            )
            messages.append(AIMessage(content=json.dumps(fn_res)))

        return chat(messages).content
