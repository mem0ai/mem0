import logging
from typing import Optional

from embedchain.config import BaseLlmConfig
from embedchain.helper.json_serializable import register_deserializable
from embedchain.llm.base import BaseLlm


@register_deserializable
class VertexAiLlm(BaseLlm):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config=config)

    def get_llm_model_answer(self, prompt):
        return VertexAiLlm._get_answer(prompt=prompt, config=self.config)

    @staticmethod
    def _get_answer(prompt: str, config: BaseLlmConfig) -> str:
        from langchain.chat_models import ChatVertexAI

        chat = ChatVertexAI(temperature=config.temperature, model=config.model)

        if config.top_p and config.top_p != 1:
            logging.warning("Config option `top_p` is not supported by this model.")

        messages = BaseLlm._get_messages(prompt, system_prompt=config.system_prompt)

        return chat(messages).content
