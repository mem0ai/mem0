import importlib
import logging
import os
from collections.abc import Generator
from typing import Any, Optional, Union

import google.generativeai as genai

from embedchain.config import BaseLlmConfig
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.llm.base import BaseLlm

logger = logging.getLogger(__name__)


@register_deserializable
class GoogleLlm(BaseLlm):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        if "GOOGLE_API_KEY" not in os.environ:
            raise ValueError("Please set the GOOGLE_API_KEY environment variable.")

        try:
            importlib.import_module("google.generativeai")
        except ModuleNotFoundError:
            raise ModuleNotFoundError(
                "The required dependencies for GoogleLlm are not installed."
                'Please install with `pip install --upgrade "embedchain[google]"`'
            ) from None

        super().__init__(config)
        genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

    def get_llm_model_answer(self, prompt):
        if self.config.system_prompt:
            raise ValueError("GoogleLlm does not support `system_prompt`")
        response = self._get_answer(prompt)
        return response

    def _get_answer(self, prompt: str) -> Union[str, Generator[Any, Any, None]]:
        model_name = self.config.model or "gemini-pro"
        logger.info(f"Using Google LLM model: {model_name}")
        model = genai.GenerativeModel(model_name=model_name)

        generation_config_params = {
            "candidate_count": 1,
            "max_output_tokens": self.config.max_tokens,
            "temperature": self.config.temperature or 0.5,
        }

        if 0.0 <= self.config.top_p <= 1.0:
            generation_config_params["top_p"] = self.config.top_p
        else:
            raise ValueError("`top_p` must be > 0.0 and < 1.0")

        generation_config = genai.types.GenerationConfig(**generation_config_params)

        response = model.generate_content(
            prompt,
            generation_config=generation_config,
            stream=self.config.stream,
        )
        if self.config.stream:
            # TODO: Implement streaming
            response.resolve()
            return response.text
        else:
            return response.text
