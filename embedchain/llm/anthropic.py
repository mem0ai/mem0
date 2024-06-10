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
        if "ANTHROPIC_API_KEY" not in os.environ:
            raise ValueError("Please set the ANTHROPIC_API_KEY environment variable.")
        super().__init__(config=config)

    def get_llm_model_answer(self, prompt):
        return AnthropicLlm._get_answer(prompt=prompt, config=self.config)

    @staticmethod
    def _get_answer(prompt: str, config: BaseLlmConfig) -> str:
        chat = ChatAnthropic(
            anthropic_api_key=os.environ["ANTHROPIC_API_KEY"], temperature=config.temperature, model_name=config.model
        )

        if config.max_tokens and config.max_tokens != 1000:
            logger.warning("Config option `max_tokens` is not supported by this model.")

        messages = BaseLlm._get_messages(prompt, system_prompt=config.system_prompt)

        return chat(messages).content
