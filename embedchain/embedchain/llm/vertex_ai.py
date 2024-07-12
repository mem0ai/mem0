import importlib
import logging
from typing import Any, Optional

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

    def get_llm_model_answer(self, prompt) -> tuple[str, Optional[dict[str, Any]]]:
        if self.config.token_usage:
            response, token_info = self._get_answer(prompt, self.config)
            model_name = "vertexai/" + self.config.model
            if model_name not in self.config.model_pricing_map:
                raise ValueError(
                    f"Model {model_name} not found in `model_prices_and_context_window.json`. \
                    You can disable token usage by setting `token_usage` to False."
                )
            total_cost = (
                self.config.model_pricing_map[model_name]["input_cost_per_token"] * token_info["prompt_token_count"]
            ) + self.config.model_pricing_map[model_name]["output_cost_per_token"] * token_info[
                "candidates_token_count"
            ]
            response_token_info = {
                "prompt_tokens": token_info["prompt_token_count"],
                "completion_tokens": token_info["candidates_token_count"],
                "total_tokens": token_info["prompt_token_count"] + token_info["candidates_token_count"],
                "total_cost": round(total_cost, 10),
                "cost_currency": "USD",
            }
            return response, response_token_info
        return self._get_answer(prompt, self.config)

    @staticmethod
    def _get_answer(prompt: str, config: BaseLlmConfig) -> str:
        if config.top_p and config.top_p != 1:
            logger.warning("Config option `top_p` is not supported by this model.")

        if config.stream:
            callbacks = config.callbacks if config.callbacks else [StreamingStdOutCallbackHandler()]
            llm = ChatVertexAI(
                temperature=config.temperature, model=config.model, callbacks=callbacks, streaming=config.stream
            )
        else:
            llm = ChatVertexAI(temperature=config.temperature, model=config.model)

        messages = VertexAILlm._get_messages(prompt)
        chat_response = llm.invoke(messages)
        if config.token_usage:
            return chat_response.content, chat_response.response_metadata["usage_metadata"]
        return chat_response.content
