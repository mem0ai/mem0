import importlib
import os
from typing import Optional

from langchain_community.llms import Together

from embedchain.config import BaseLlmConfig
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.llm.base import BaseLlm


@register_deserializable
class TogetherLlm(BaseLlm):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        if "TOGETHER_API_KEY" not in os.environ:
            raise ValueError("Please set the TOGETHER_API_KEY environment variable.")

        try:
            importlib.import_module("together")
        except ModuleNotFoundError:
            raise ModuleNotFoundError(
                "The required dependencies for Together are not installed."
                'Please install with `pip install --upgrade "embedchain[together]"`'
            ) from None

        super().__init__(config=config)

    def get_llm_model_answer(self, prompt):
        if self.config.system_prompt:
            raise ValueError("TogetherLlm does not support `system_prompt`")
        return TogetherLlm._get_answer(prompt=prompt, config=self.config)

    @staticmethod
    def _get_answer(prompt: str, config: BaseLlmConfig) -> str:
        llm = Together(
            together_api_key=os.environ["TOGETHER_API_KEY"],
            model=config.model,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            top_p=config.top_p,
        )

        return llm.invoke(prompt)
