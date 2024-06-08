import importlib
import os
from typing import Optional, Any

from langchain_cohere import ChatCohere

from embedchain.config import BaseLlmConfig
from embedchain.helpers.json_serializable import register_deserializable
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
                'Please install with `pip install langchain_cohere==1.16.0`'
            ) from None

        super().__init__(config=config)

    def get_llm_model_answer(self, prompt) -> tuple[str, Optional[dict[str, Any]]]:
        if self.config.system_prompt:
            raise ValueError("CohereLlm does not support `system_prompt`")
        
        response, token_info = self._get_answer(prompt, self.config)
        if self.config.token_usage:
            model_name = "cohere/" + self.config.model
            total_cost = (self.config.model_pricing_map[model_name]["input_cost_per_token"] * token_info["input_tokens"]) + self.config.model_pricing_map[model_name]["output_cost_per_token"] * token_info["output_tokens"]
            response_token_info = {"input_tokens": token_info["input_tokens"], "output_tokens": token_info["output_tokens"], "total_cost (USD)": round(total_cost, 10)}
            return response, response_token_info
        return response, None

    @staticmethod
    def _get_answer(prompt: str, config: BaseLlmConfig) -> str:
        api_key = config.api_key or os.environ["COHERE_API_KEY"]
        kwargs = {
            "model_name": config.model or "command-r",
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "together_api_key": api_key,
        }
        
        chat = ChatCohere(**kwargs)
        chat_response = chat.invoke(prompt)
        return chat_response.content, chat_response.response_metadata["token_count"]
