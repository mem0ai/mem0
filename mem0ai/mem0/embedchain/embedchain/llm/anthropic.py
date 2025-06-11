import logging
import os
from typing import Any, Optional

try:
    from langchain_anthropic import ChatAnthropic
except ImportError:
    raise ImportError("Please install the langchain-anthropic package by running `pip install langchain-anthropic`.")

from embedchain.config import BaseLlmConfig
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.llm.base import BaseLlm

logger = logging.getLogger(__name__)


@register_deserializable
class AnthropicLlm(BaseLlm):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config=config)
        if not self.config.api_key and "ANTHROPIC_API_KEY" not in os.environ:
            raise ValueError("Please set the ANTHROPIC_API_KEY environment variable or pass it in the config.")

    def get_llm_model_answer(self, prompt) -> tuple[str, Optional[dict[str, Any]]]:
        if self.config.token_usage:
            response, token_info = self._get_answer(prompt, self.config)
            model_name = "anthropic/" + self.config.model
            if model_name not in self.config.model_pricing_map:
                raise ValueError(
                    f"Model {model_name} not found in `model_prices_and_context_window.json`. \
                    You can disable token usage by setting `token_usage` to False."
                )
            total_cost = (
                self.config.model_pricing_map[model_name]["input_cost_per_token"] * token_info["input_tokens"]
            ) + self.config.model_pricing_map[model_name]["output_cost_per_token"] * token_info["output_tokens"]
            response_token_info = {
                "prompt_tokens": token_info["input_tokens"],
                "completion_tokens": token_info["output_tokens"],
                "total_tokens": token_info["input_tokens"] + token_info["output_tokens"],
                "total_cost": round(total_cost, 10),
                "cost_currency": "USD",
            }
            return response, response_token_info
        return self._get_answer(prompt, self.config)

    @staticmethod
    def _get_answer(prompt: str, config: BaseLlmConfig) -> str:
        api_key = config.api_key or os.getenv("ANTHROPIC_API_KEY")
        chat = ChatAnthropic(anthropic_api_key=api_key, temperature=config.temperature, model_name=config.model)

        if config.max_tokens and config.max_tokens != 1000:
            logger.warning("Config option `max_tokens` is not supported by this model.")

        messages = BaseLlm._get_messages(prompt, system_prompt=config.system_prompt)

        chat_response = chat.invoke(messages)
        if config.token_usage:
            return chat_response.content, chat_response.response_metadata["token_usage"]
        return chat_response.content
