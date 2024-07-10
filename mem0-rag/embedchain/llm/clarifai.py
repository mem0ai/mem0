import logging
import os
from typing import Optional

from embedchain.config import BaseLlmConfig
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.llm.base import BaseLlm


@register_deserializable
class ClarifaiLlm(BaseLlm):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config=config)
        if not self.config.api_key and "CLARIFAI_PAT" not in os.environ:
            raise ValueError("Please set the CLARIFAI_PAT environment variable.")

    def get_llm_model_answer(self, prompt):
        return self._get_answer(prompt=prompt, config=self.config)

    @staticmethod
    def _get_answer(prompt: str, config: BaseLlmConfig) -> str:
        try:
            from clarifai.client.model import Model
        except ModuleNotFoundError:
            raise ModuleNotFoundError(
                "The required dependencies for Clarifai are not installed."
                "Please install with `pip install clarifai==10.0.1`"
            ) from None

        model_name = config.model
        logging.info(f"Using clarifai LLM model: {model_name}")
        api_key = config.api_key or os.getenv("CLARIFAI_PAT")
        model = Model(url=model_name, pat=api_key)
        params = config.model_kwargs

        try:
            (params := {}) if config.model_kwargs is None else config.model_kwargs
            predict_response = model.predict_by_bytes(
                bytes(prompt, "utf-8"),
                input_type="text",
                inference_params=params,
            )
            text = predict_response.outputs[0].data.text.raw
            return text

        except Exception as e:
            logging.error(f"Predict failed, exception: {e}")
