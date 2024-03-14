import importlib
import logging
from typing import Optional

from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain_google_vertexai import ChatVertexAI

from embedchain.config import BaseLlmConfig
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.llm.base import BaseLlm

logger = logging.getLogger(__name__)


@register_deserializable
class VertexAILlm(BaseLlm):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        try:
            importlib.import_module("vertexai")
        except ModuleNotFoundError:
            raise ModuleNotFoundError(
                "The required dependencies for VertexAI are not installed."
                'Please install with `pip install --upgrade "embedchain[vertexai]"`'
            ) from None
        super().__init__(config=config)

    def get_llm_model_answer(self, prompt):
        return VertexAILlm._get_answer(prompt=prompt, config=self.config)

    @staticmethod
    def _get_answer(prompt: str, config: BaseLlmConfig) -> str:
        if config.top_p and config.top_p != 1:
            logger.warning("Config option `top_p` is not supported by this model.")

        messages = BaseLlm._get_messages(prompt, system_prompt=config.system_prompt)

        if config.stream:
            callbacks = config.callbacks if config.callbacks else [StreamingStdOutCallbackHandler()]
            llm = ChatVertexAI(
                temperature=config.temperature, model=config.model, callbacks=callbacks, streaming=config.stream
            )
        else:
            llm = ChatVertexAI(temperature=config.temperature, model=config.model)

        return llm.invoke(messages).content
