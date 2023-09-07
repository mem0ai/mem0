import os
from typing import Optional

from embedchain.config import BaseLlmConfig
from embedchain.helper_classes.json_serializable import register_deserializable
from embedchain.llm.base_llm import BaseLlm


@register_deserializable
class PalmLlm(BaseLlm):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config=config)

    def get_llm_model_answer(self, prompt):
        return PalmLlm._get_athrophic_answer(prompt=prompt, config=self.config)

    @staticmethod
    def _get_athrophic_answer(prompt: str, config: BaseLlmConfig) -> str:
        if os.getenv("GOOGLE_API_KEY") is None:
            raise ValueError("GOOGLE_API_KEY environment variables not provided")

        from langchain.chat_models import ChatGooglePalm

        model = "models/chat-bison-001"
        if (config is not None) and (config.model is not None):
            model = config.model

        chat = ChatGooglePalm(temperature=config.temperature, top_p=config.top_p, model_name=model)
        messages = BaseLlm._get_messages(prompt, system_prompt=config.system_prompt)

        return chat(messages).content
