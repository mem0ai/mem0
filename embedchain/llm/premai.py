import importlib
import os
from typing import Any, Optional

from langchain_community.chat_models.premai import ChatPremAI
from langchain_core.messages import HumanMessage, SystemMessage

from embedchain.config import BaseLlmConfig
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.llm.base import BaseLlm


class PremAIConfig(BaseLlmConfig):
    def __init__(self, project_id: int, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.project_id = project_id


@register_deserializable
class PremAILlm(BaseLlm):
    def __init__(self, config: Optional[PremAIConfig] = None):
        super().__init__(config=config)
        try:
            importlib.import_module("premai")
        except ModuleNotFoundError:
            raise ModuleNotFoundError(
                "The required dependencies for PremAI are not installed."
                'Please install with `pip install --upgrade "embedchain[premai]"`'
            ) from None

        _api_key = self.config.api_key or os.environ.get("PREMAI_API_KEY")
        if _api_key is None:
            raise ValueError("Please set PREMAI_API_KEY environment variable or pass in the config.")
        os.environ["PREMAI_API_KEY"] = _api_key

        self.client = ChatPremAI(project_id=config.project_id)

    def get_llm_model_answer(self, prompt: str) -> str:
        return PremAILlm._get_answer(client=self.client, config=self.config, prompt=prompt)

    @staticmethod
    def _get_answer(client: Any, prompt: str, config: BaseLlmConfig) -> str:
        messages = []
        if config.system_prompt:
            messages.append(SystemMessage(content=config.system_prompt))
        messages.append(HumanMessage(content=prompt))
        kwargs = {"temperature": config.temperature, "max_tokens": config.max_tokens, "top_p": config.top_p}

        if config.stream:
            response = ""
            for chunk in client.stream(input=messages, **kwargs):
                response += chunk.content
        else:
            response = client.invoke(input=messages, **kwargs)
        return response.content
