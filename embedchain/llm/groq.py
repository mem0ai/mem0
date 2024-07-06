import os
from typing import Any, Optional

from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.schema import HumanMessage, SystemMessage

try:
    from langchain_groq import ChatGroq
except ImportError:
    raise ImportError("Groq requires extra dependencies. Install with `pip install langchain-groq`") from None


from embedchain.config import BaseLlmConfig
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.llm.base import BaseLlm


@register_deserializable
class GroqLlm(BaseLlm):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config=config)
        if not self.config.api_key and "GROQ_API_KEY" not in os.environ:
            raise ValueError("Please set the GROQ_API_KEY environment variable or pass it in the config.")

    def get_llm_model_answer(self, prompt) -> tuple[str, Optional[dict[str, Any]]]:
        if self.config.token_usage:
            response, token_info = self._get_answer(prompt, self.config)
            model_name = "groq/" + self.config.model
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

    def _get_answer(self, prompt: str, config: BaseLlmConfig) -> str:
        messages = []
        if config.system_prompt:
            messages.append(SystemMessage(content=config.system_prompt))
        messages.append(HumanMessage(content=prompt))
        api_key = config.api_key or os.environ["GROQ_API_KEY"]
        kwargs = {
            "model_name": config.model or "mixtral-8x7b-32768",
            "temperature": config.temperature,
            "groq_api_key": api_key,
        }
        if config.stream:
            callbacks = config.callbacks if config.callbacks else [StreamingStdOutCallbackHandler()]
            chat = ChatGroq(**kwargs, streaming=config.stream, callbacks=callbacks, api_key=api_key)
        else:
            chat = ChatGroq(**kwargs)

        chat_response = chat.invoke(prompt)
        if self.config.token_usage:
            return chat_response.content, chat_response.response_metadata["token_usage"]
        return chat_response.content
