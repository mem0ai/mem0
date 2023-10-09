import importlib
import os
from typing import Optional

from langchain.llms import Cohere

from embedchain.config import BaseLlmConfig
from embedchain.helper.json_serializable import register_deserializable
from embedchain.llm.base import BaseLlm


@register_deserializable
class CohereLlm(BaseLlm):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        if "COHERE_API_KEY" not in os.environ:
            raise ValueError("Please set the COHERE_API_KEY environment variable.")

        try:
            importlib.import_module("cohere")
        except ModuleNotFoundError:
            raise ModuleNotFoundError(
                "The required dependencies for Cohere are not installed."
                'Please install with `pip install --upgrade "embedchain[cohere]"`'
            ) from None

        super().__init__(config=config)

    def get_llm_model_answer(self, prompt):
        if self.config.system_prompt:
            raise ValueError("CohereLlm does not support `system_prompt`")
        return CohereLlm._get_answer(prompt=prompt, config=self.config)

    @staticmethod
    def _get_answer(prompt: str, config: BaseLlmConfig) -> str:
        llm = Cohere(
            cohere_api_key=os.environ["COHERE_API_KEY"],
            model=config.model,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            p=config.top_p,
        )

        return llm(prompt)
