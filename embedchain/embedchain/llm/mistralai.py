import os
from typing import Any, Optional

from embedchain.config import BaseLlmConfig
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.llm.base import BaseLlm


@register_deserializable
class MistralAILlm(BaseLlm):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config)
        if not self.config.api_key and "MISTRAL_API_KEY" not in os.environ:
            raise ValueError("Please set the MISTRAL_API_KEY environment variable or pass it in the config.")

    def get_llm_model_answer(self, prompt) -> tuple[str, Optional[dict[str, Any]]]:
        if self.config.token_usage:
            response, token_info = self._get_answer(prompt, self.config)
            model_name = "mistralai/" + self.config.model
            if model_name not in self.config.model_pricing_map:
                raise ValueError(
                    f"Model {model_name} not found in `model_prices_and_context_window.json`. \
                    You can disable token usage by setting `token_usage` to False."
                )
            total_cost = (
                self.config.model_pricing_map[model_name]["input_cost_per_token"] * token_info["prompt_tokens"]
            ) + self.config.model_pricing_map[model_name]["output_cost_per_token"] * token_info["completion_tokens"]
            response_token_info = {
                "prompt_tokens": token_info["prompt_tokens"],
                "completion_tokens": token_info["completion_tokens"],
                "total_tokens": token_info["prompt_tokens"] + token_info["completion_tokens"],
                "total_cost": round(total_cost, 10),
                "cost_currency": "USD",
            }
            return response, response_token_info
        return self._get_answer(prompt, self.config)

    @staticmethod
    def _get_answer(prompt: str, config: BaseLlmConfig):
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            from langchain_mistralai.chat_models import ChatMistralAI
        except ModuleNotFoundError:
            raise ModuleNotFoundError(
                "The required dependencies for MistralAI are not installed."
                'Please install with `pip install --upgrade "embedchain[mistralai]"`'
            ) from None

        api_key = config.api_key or os.getenv("MISTRAL_API_KEY")
        client = ChatMistralAI(mistral_api_key=api_key)
        messages = []
        if config.system_prompt:
            messages.append(SystemMessage(content=config.system_prompt))
        messages.append(HumanMessage(content=prompt))
        kwargs = {
            "model": config.model or "mistral-tiny",
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "top_p": config.top_p,
        }

        # TODO: Add support for streaming
        if config.stream:
            answer = ""
            for chunk in client.stream(**kwargs, input=messages):
                answer += chunk.content
            return answer
        else:
            chat_response = client.invoke(**kwargs, input=messages)
            if config.token_usage:
                return chat_response.content, chat_response.response_metadata["token_usage"]
            return chat_response.content
