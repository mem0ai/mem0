import os
from collections.abc import Iterable
from typing import Optional, Union, Any

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
        if "NVIDIA_API_KEY" not in os.environ:
            raise ValueError("NVIDIA_API_KEY environment variable must be set")

        super().__init__(config=config)

    def get_llm_model_answer(self, prompt) -> tuple[str, Optional[dict[str, Any]]]:
        response, token_info = self._get_answer(prompt, self.config)
        if self.config.token_usage:
            model_name = "nvidia/" + self.config.model
            total_cost = (self.config.model_pricing_map[model_name]["input_cost_per_token"] * token_info["input_tokens"]) + self.config.model_pricing_map[model_name]["output_cost_per_token"] * token_info["output_tokens"]
            response_token_info = {"input_tokens": token_info["input_tokens"], "output_tokens": token_info["output_tokens"], "total_cost (USD)": round(total_cost, 10)}
            return response, response_token_info
        return response, None

    @staticmethod
    def _get_answer(prompt: str, config: BaseLlmConfig) -> Union[str, Iterable]:
        callback_manager = [StreamingStdOutCallbackHandler()] if config.stream else [StdOutCallbackHandler()]
        model_kwargs = config.model_kwargs or {}
        labels = model_kwargs.get("labels", None)
        params = {"model": config.model}
        if config.system_prompt:
            params["system_prompt"] = config.system_prompt
        if config.temperature:
            params["temperature"] = config.temperature
        if config.top_p:
            params["top_p"] = config.top_p
        if labels:
            params["labels"] = labels
        llm = ChatNVIDIA(**params, callback_manager=CallbackManager(callback_manager))
        chat_response = llm.invoke(prompt) if labels is None else llm.invoke(prompt, labels=labels)
        return chat_response.content, chat_response.response_metadata["token_usage"]
