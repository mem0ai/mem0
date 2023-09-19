import logging
from typing import Optional

from embedchain.config import BaseLlmConfig
from embedchain.helper.json_serializable import register_deserializable
from embedchain.llm.base import BaseLlm


@register_deserializable
class AntrophicLlm(BaseLlm):
    # FIXME: Assign default model
    DEFAULT_MODEL = None

    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config=config)
        if self.config.model is None:
            self.config.model = AntrophicLlm.DEFAULT_MODEL

    def get_llm_model_answer(self, prompt):
        return AntrophicLlm._get_athrophic_answer(prompt=prompt, config=self.config)

    @staticmethod
    def _get_athrophic_answer(prompt: str, config: BaseLlmConfig) -> str:
        from langchain.chat_models import ChatAnthropic

        chat = ChatAnthropic(temperature=config.temperature, model=config.model or AntrophicLlm.DEFAULT_MODEL)

        if config.max_tokens and config.max_tokens != 1000:
            logging.warning("Config option `max_tokens` is not supported by this model.")

        messages = BaseLlm._get_messages(prompt, system_prompt=config.system_prompt)

        return chat(messages).content
