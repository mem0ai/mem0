import importlib
import logging
import os
from typing import Optional

from langchain_community.llms.huggingface_endpoint import HuggingFaceEndpoint
from langchain_community.llms.huggingface_hub import HuggingFaceHub
from langchain_community.llms.huggingface_pipeline import HuggingFacePipeline

from embedchain.config import BaseLlmConfig
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.llm.base import BaseLlm

logger = logging.getLogger(__name__)


@register_deserializable
class HuggingFaceLlm(BaseLlm):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        if "HUGGINGFACE_ACCESS_TOKEN" not in os.environ:
            raise ValueError("Please set the HUGGINGFACE_ACCESS_TOKEN environment variable.")

        try:
            importlib.import_module("huggingface_hub")
        except ModuleNotFoundError:
            raise ModuleNotFoundError(
                "The required dependencies for HuggingFaceHub are not installed."
                'Please install with `pip install --upgrade "embedchain[huggingface-hub]"`'
            ) from None

        super().__init__(config=config)

    def get_llm_model_answer(self, prompt):
        if self.config.system_prompt:
            raise ValueError("HuggingFaceLlm does not support `system_prompt`")
        return HuggingFaceLlm._get_answer(prompt=prompt, config=self.config)

    @staticmethod
    def _get_answer(prompt: str, config: BaseLlmConfig) -> str:
        # If the user wants to run the model locally, they can do so by setting the `local` flag to True
        if config.model and config.local:
            return HuggingFaceLlm._from_pipeline(prompt=prompt, config=config)
        elif config.model:
            return HuggingFaceLlm._from_model(prompt=prompt, config=config)
        elif config.endpoint:
            return HuggingFaceLlm._from_endpoint(prompt=prompt, config=config)
        else:
            raise ValueError("Either `model` or `endpoint` must be set in config")

    @staticmethod
    def _from_model(prompt: str, config: BaseLlmConfig) -> str:
        model_kwargs = {
            "temperature": config.temperature or 0.1,
            "max_new_tokens": config.max_tokens,
        }

        if 0.0 < config.top_p < 1.0:
            model_kwargs["top_p"] = config.top_p
        else:
            raise ValueError("`top_p` must be > 0.0 and < 1.0")

        model = config.model
        logger.info(f"Using HuggingFaceHub with model {model}")
        llm = HuggingFaceHub(
            huggingfacehub_api_token=os.environ["HUGGINGFACE_ACCESS_TOKEN"],
            repo_id=model,
            model_kwargs=model_kwargs,
        )
        return llm.invoke(prompt)

    @staticmethod
    def _from_endpoint(prompt: str, config: BaseLlmConfig) -> str:
        llm = HuggingFaceEndpoint(
            huggingfacehub_api_token=os.environ["HUGGINGFACE_ACCESS_TOKEN"],
            endpoint_url=config.endpoint,
            task="text-generation",
            model_kwargs=config.model_kwargs,
        )
        return llm.invoke(prompt)

    @staticmethod
    def _from_pipeline(prompt: str, config: BaseLlmConfig) -> str:
        model_kwargs = {
            "temperature": config.temperature or 0.1,
            "max_new_tokens": config.max_tokens,
        }

        if 0.0 < config.top_p < 1.0:
            model_kwargs["top_p"] = config.top_p
        else:
            raise ValueError("`top_p` must be > 0.0 and < 1.0")

        llm = HuggingFacePipeline.from_model_id(
            model_id=config.model,
            task="text-generation",
            pipeline_kwargs=model_kwargs,
        )
        return llm.invoke(prompt)
