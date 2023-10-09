import importlib
import os
from typing import Optional

from langchain.llms import HuggingFaceHub

from embedchain.config import BaseLlmConfig
from embedchain.helper.json_serializable import register_deserializable
from embedchain.llm.base import BaseLlm


@register_deserializable
class HuggingFaceHubLlm(BaseLlm):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        if "HUGGINGFACEHUB_ACCESS_TOKEN" not in os.environ:
            raise ValueError("Please set the HUGGINGFACEHUB_ACCESS_TOKEN environment variable.")

        try:
            importlib.import_module("huggingface_hub")
        except ModuleNotFoundError:
            raise ModuleNotFoundError(
                "The required dependencies for HuggingFaceHub are not installed."
                'Please install with `pip install --upgrade "embedchain[huggingface_hub]"`'
            ) from None

        super().__init__(config=config)

    def get_llm_model_answer(self, prompt):
        if self.config.system_prompt:
            raise ValueError("HuggingFaceHubLlm does not support `system_prompt`")
        return HuggingFaceHubLlm._get_answer(prompt=prompt, config=self.config)

    @staticmethod
    def _get_answer(prompt: str, config: BaseLlmConfig) -> str:
        model_kwargs = {
            "temperature": config.temperature or 0.1,
            "max_new_tokens": config.max_tokens,
        }

        if config.top_p > 0.0 and config.top_p < 1.0:
            model_kwargs["top_p"] = config.top_p
        else:
            raise ValueError("`top_p` must be > 0.0 and < 1.0")

        llm = HuggingFaceHub(
            huggingfacehub_api_token=os.environ["HUGGINGFACEHUB_ACCESS_TOKEN"],
            repo_id=config.model or "google/flan-t5-xxl",
            model_kwargs=model_kwargs,
        )

        return llm(prompt)
