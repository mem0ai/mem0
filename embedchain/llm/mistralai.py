import os
from typing import Optional

from embedchain.config import BaseLlmConfig
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.llm.base import BaseLlm


@register_deserializable
class MistralAILlm(BaseLlm):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config)

    def get_llm_model_answer(self, prompt):
        return MistralAILlm._get_answer(prompt=prompt, config=self.config)

    @staticmethod
    def _get_answer(prompt: str, config: BaseLlmConfig):
        try:
            from mistralai.client import MistralClient
            from mistralai.models.chat_completion import ChatMessage
        except ModuleNotFoundError:
            raise ModuleNotFoundError(
                "The required dependencies for MistralAI are not installed."
                'Please install with `pip install --upgrade "embedchain[mistral]"`'
            ) from None
        api_key = config.api_key or os.environ["MISTRAL_API_KEY"]
        client = MistralClient(api_key=api_key)
        messages = []
        if config.system_prompt:
            messages.append(ChatMessage(role="system", content=config.system_prompt))
        messages.append(ChatMessage(role="human", content=prompt))
        kwargs = {
            "model": config.model or "mistral-tiny",
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "top_p": config.top_p,
        }

        if config.stream:
            for chunk in client.chat_stream(**kwargs, messages=messages):
                answer = chunk.choices[0].delta.content
                yield answer
        else:
            response = client.chat(**kwargs, messages=messages)
            answer = response.choices[0].message.content
            return answer
