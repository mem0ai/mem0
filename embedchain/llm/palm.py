import os
from importlib.util import find_spec
from typing import Optional

from embedchain.config import BaseLlmConfig
from embedchain.helper.json_serializable import register_deserializable
from embedchain.llm.base import BaseLlm


@register_deserializable
class PalmLlm(BaseLlm):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        if find_spec("google.generativeai") is None:
            raise ModuleNotFoundError(
                "The google-generativeai python package is not installed. Please install it with `pip install --upgrade embedchain[palm]`"  # noqa E501
            )
        super().__init__(config=config)

    def get_llm_model_answer(self, prompt):
        return PalmLlm._get_athrophic_answer(prompt=prompt, config=self.config)

    @staticmethod
    def _get_athrophic_answer(prompt: str, config: BaseLlmConfig) -> str:
        if os.getenv("GOOGLE_API_KEY") is None:
            raise ValueError("GOOGLE_API_KEY environment variables not provided")

        from langchain.chat_models import ChatGooglePalm

        if not config.model:
            config.model = "models/chat-bison-001"

        chat = ChatGooglePalm(temperature=config.temperature, top_p=config.top_p, model_name=config.model)
        messages = BaseLlm._get_messages(prompt, system_prompt=config.system_prompt)

        return chat(messages).content
