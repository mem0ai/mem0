import os
from typing import Optional

from langchain.schema import HumanMessage, SystemMessage
from langchain_community.chat_models import JinaChat

from embedchain.config import BaseLlmConfig
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.llm.base import BaseLlm


@register_deserializable
class JinaLlm(BaseLlm):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config=config)
        if not self.config.api_key and "JINACHAT_API_KEY" not in os.environ:
            raise ValueError("Please set the JINACHAT_API_KEY environment variable or pass it in the config.")

    def get_llm_model_answer(self, prompt):
        response = JinaLlm._get_answer(prompt, self.config)
        return response

    @staticmethod
    def _get_answer(prompt: str, config: BaseLlmConfig) -> str:
        messages = []
        if config.system_prompt:
            messages.append(SystemMessage(content=config.system_prompt))
        messages.append(HumanMessage(content=prompt))
        kwargs = {
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "jinachat_api_key": config.api_key or os.environ["JINACHAT_API_KEY"],
            "model_kwargs": {},
        }
        if config.top_p:
            kwargs["model_kwargs"]["top_p"] = config.top_p
        if config.stream:
            from langchain.callbacks.streaming_stdout import (
                StreamingStdOutCallbackHandler,
            )

            chat = JinaChat(**kwargs, streaming=config.stream, callbacks=[StreamingStdOutCallbackHandler()])
        else:
            chat = JinaChat(**kwargs)
        return chat(messages).content
