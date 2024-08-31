import os
from typing import Optional

from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain_community.llms.octoai_endpoint import OctoAIEndpoint

from embedchain.config import BaseLlmConfig
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.llm.base import BaseLlm


@register_deserializable
class OctoAILlm(BaseLlm):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        assert "OCTOAI_API_TOKEN" in os.environ or config.api_key, \
            "Please set OCTOAI_API_TOKEN as environment variable."
        super().__init__(config=config)

    def get_llm_model_answer(self, prompt):
        return self._get_answer(prompt, self.config)

    @staticmethod
    def _get_answer(prompt: str, config: BaseLlmConfig) -> str:
        chat = OctoAIEndpoint(
            model_name=config.model,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            top_p=config.top_p,
            streaming=config.stream,
            callbacks=config.callbacks
            if (not config.stream) or (config.stream and config.callbacks)
            else [StreamingStdOutCallbackHandler()],
        )

        return chat.invoke(prompt)
