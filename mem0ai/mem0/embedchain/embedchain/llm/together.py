import importlib
import os
from typing import Any, Optional

try:
    from langchain_together import ChatTogether
except ImportError:
    raise ImportError(
        "Please install the langchain_together package by running `pip install langchain_together==0.1.3`."
    )

from embedchain.config import BaseLlmConfig
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.llm.base import BaseLlm


@register_deserializable
class TogetherLlm(BaseLlm):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        try:
            importlib.import_module("together")
        except ModuleNotFoundError:
            raise ModuleNotFoundError(
                "The required dependencies for Together are not installed."
                'Please install with `pip install --upgrade "embedchain[together]"`'
            ) from None

        super().__init__(config=config)
        if not self.config.api_key and "TOGETHER_API_KEY" not in os.environ:
            raise ValueError("Please set the TOGETHER_API_KEY environment variable or pass it in the config.")

    def get_llm_model_answer(self, prompt) -> tuple[str, Optional[dict[str, Any]]]:
        if self.config.system_prompt:
            raise ValueError("TogetherLlm does not support `system_prompt`")

        if self.config.token_usage:
            response, token_info = self._get_answer(prompt, self.config)
            model_name = "together/" + self.config.model
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

    @staticmethod
    def _get_answer(prompt: str, config: BaseLlmConfig) -> str:
        api_key = config.api_key or os.environ["TOGETHER_API_KEY"]
        kwargs = {
            "model_name": config.model or "mixtral-8x7b-32768",
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "together_api_key": api_key,
        }

        chat = ChatTogether(**kwargs)
        chat_response = chat.invoke(prompt)
        if config.token_usage:
            return chat_response.content, chat_response.response_metadata["token_usage"]
        return chat_response.content
