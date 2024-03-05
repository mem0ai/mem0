from collections.abc import Iterable
from typing import Optional, Union

from langchain.callbacks.manager import CallbackManager
from langchain.callbacks.stdout import StdOutCallbackHandler
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain_community.llms.ollama import Ollama

from embedchain.config import BaseLlmConfig
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.llm.base import BaseLlm


@register_deserializable
class OllamaLlm(BaseLlm):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config=config)
        if self.config.model is None:
            self.config.model = "llama2"

    def get_llm_model_answer(self, prompt):
        return self._get_answer(prompt=prompt, config=self.config)

    @staticmethod
    def _get_answer(prompt: str, config: BaseLlmConfig) -> Union[str, Iterable]:
        callback_manager = [StreamingStdOutCallbackHandler()] if config.stream else [StdOutCallbackHandler()]

        llm = Ollama(
            model=config.model,
            system=config.system_prompt,
            temperature=config.temperature,
            top_p=config.top_p,
            callback_manager=CallbackManager(callback_manager),
            base_url=config.base_url,
        )

        return llm.invoke(prompt)
