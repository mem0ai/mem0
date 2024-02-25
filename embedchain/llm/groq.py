import os
from typing import Optional

from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.schema import HumanMessage, SystemMessage

try:
    from langchain_groq import ChatGroq
except ImportError:
    raise ImportError("Groq requires extra dependencies. Install with `pip install langchain-groq`") from None


from embedchain.config import BaseLlmConfig
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.llm.base import BaseLlm


@register_deserializable
class GroqLlm(BaseLlm):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config=config)

    def get_llm_model_answer(self, prompt) -> str:
        response = self._get_answer(prompt, self.config)
        return response

    def _get_answer(self, prompt: str, config: BaseLlmConfig) -> str:
        messages = []
        if config.system_prompt:
            messages.append(SystemMessage(content=config.system_prompt))
        messages.append(HumanMessage(content=prompt))
        api_key = config.api_key or os.environ["GROQ_API_KEY"]
        kwargs = {
            "model_name": config.model or "mixtral-8x7b-32768",
            "temperature": config.temperature,
            "groq_api_key": api_key,
        }
        if config.stream:
            callbacks = config.callbacks if config.callbacks else [StreamingStdOutCallbackHandler()]
            chat = ChatGroq(**kwargs, streaming=config.stream, callbacks=callbacks, api_key=api_key)
        else:
            chat = ChatGroq(**kwargs)
        return chat.invoke(messages).content
