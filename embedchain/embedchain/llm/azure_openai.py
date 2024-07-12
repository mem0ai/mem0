import logging
from typing import Optional

from embedchain.config import BaseLlmConfig
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.llm.base import BaseLlm

logger = logging.getLogger(__name__)


@register_deserializable
class AzureOpenAILlm(BaseLlm):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config=config)

    def get_llm_model_answer(self, prompt):
        return self._get_answer(prompt=prompt, config=self.config)

    @staticmethod
    def _get_answer(prompt: str, config: BaseLlmConfig) -> str:
        from langchain_openai import AzureChatOpenAI

        if not config.deployment_name:
            raise ValueError("Deployment name must be provided for Azure OpenAI")

        chat = AzureChatOpenAI(
            deployment_name=config.deployment_name,
            openai_api_version=str(config.api_version) if config.api_version else "2024-02-01",
            model_name=config.model or "gpt-3.5-turbo",
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            streaming=config.stream,
        )

        if config.top_p and config.top_p != 1:
            logger.warning("Config option `top_p` is not supported by this model.")

        messages = BaseLlm._get_messages(prompt, system_prompt=config.system_prompt)

        return chat.invoke(messages).content
