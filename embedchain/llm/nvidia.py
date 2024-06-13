import os
from collections.abc import Iterable
from typing import Optional, Union

from langchain.callbacks.manager import CallbackManager
from langchain.callbacks.stdout import StdOutCallbackHandler
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler

try:
    from langchain_nvidia_ai_endpoints import ChatNVIDIA
except ImportError:
    raise ImportError(
        "NVIDIA AI endpoints requires extra dependencies. Install with `pip install langchain-nvidia-ai-endpoints`"
    ) from None

from embedchain.config import BaseLlmConfig
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.llm.base import BaseLlm


@register_deserializable
class NvidiaLlm(BaseLlm):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config=config)
        if not self.config.api_key and "NVIDIA_API_KEY" not in os.environ:
            raise ValueError("Please set the NVIDIA_API_KEY environment variable or pass it in the config.")

    def get_llm_model_answer(self, prompt):
        return self._get_answer(prompt=prompt, config=self.config)

    @staticmethod
    def _get_answer(prompt: str, config: BaseLlmConfig) -> Union[str, Iterable]:
        callback_manager = [StreamingStdOutCallbackHandler()] if config.stream else [StdOutCallbackHandler()]
        model_kwargs = config.model_kwargs or {}
        labels = model_kwargs.get("labels", None)
        params = {"model": config.model, "nvidia_api_key": config.api_key or os.getenv("NVIDIA_API_KEY")}
        if config.system_prompt:
            params["system_prompt"] = config.system_prompt
        if config.temperature:
            params["temperature"] = config.temperature
        if config.top_p:
            params["top_p"] = config.top_p
        if labels:
            params["labels"] = labels
        llm = ChatNVIDIA(**params, callback_manager=CallbackManager(callback_manager))
        return llm.invoke(prompt).content if labels is None else llm.invoke(prompt, labels=labels).content
