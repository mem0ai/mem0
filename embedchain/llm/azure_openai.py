import logging
from typing import Optional

from embedchain.config import BaseLlmConfig
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.llm.base import BaseLlm


@register_deserializable
class AzureOpenAILlm(BaseLlm):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config=config)

    def get_llm_model_answer(self, prompt):
        return AzureOpenAILlm._get_answer(prompt=prompt, config=self.config)

    @staticmethod
    def _get_answer(prompt: str, config: BaseLlmConfig) -> str:
        from langchain.chat_models import AzureChatOpenAI

        if not config.deployment_name:
            raise ValueError("Deployment name must be provided for Azure OpenAI")

        chat = AzureChatOpenAI(
            deployment_name=config.deployment_name,
            openai_api_version="2023-05-15",
            model_name=config.model or "gpt-3.5-turbo",
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            streaming=config.stream,
        )

        if config.top_p and config.top_p != 1:
            logging.warning("Config option `top_p` is not supported by this model.")

        messages = BaseLlm._get_messages(prompt, system_prompt=config.system_prompt)

        return chat(messages).content
