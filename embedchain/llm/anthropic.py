import logging
import os
from typing import Optional

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

    def get_llm_model_answer(self, prompt):
        return AnthropicLlm._get_answer(prompt=prompt, config=self.config)

    @staticmethod
    def _get_answer(prompt: str, config: BaseLlmConfig) -> str:
        api_key = config.api_key or os.getenv("ANTHROPIC_API_KEY")
        chat = ChatAnthropic(anthropic_api_key=api_key, temperature=config.temperature, model_name=config.model)

        if config.max_tokens and config.max_tokens != 1000:
            logger.warning("Config option `max_tokens` is not supported by this model.")

        messages = BaseLlm._get_messages(prompt, system_prompt=config.system_prompt)

        return chat(messages).content
