import os
import logging
from typing import Any, Optional

from langchain.chat_models import BedrockChat
from langchain.schema import HumanMessage, SystemMessage

from embedchain.config import BaseLlmConfig
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.llm.base import BaseLlm


@register_deserializable
class AWSBedrockLlm(BaseLlm):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        super().__init__(config)
    
    def get_llm_model_answer(self, prompt) -> str:
        response = self._get_answer(prompt, self.config)
        return response
    
    
    def _get_answer(self, prompt: str, config: BaseLlmConfig) -> str:
        try:
            import boto3
        except ModuleNotFoundError:
            raise ModuleNotFoundError(
                "The required dependencies for AWSBedrock are not installed."
                'Please install with `pip install --upgrade "embedchain[aws-bedrock]"`'
            ) from None
        
        self.boto_client = boto3.client('bedrock', 'us-west-2')
        
        messages = []
        if config.system_prompt:
            messages.append(SystemMessage(content=config.system_prompt))
        messages.append(HumanMessage(content=prompt))
        kwargs = {
            "model_id": config.model or "anthropic.claude-v2",
            "client": self.boto_client,
            "model_kwargs": {
                "temperature": config.temperature,
                "max_tokens_to_sample": config.max_tokens,
            },
        }
        if config.top_p:
            kwargs["model_kwargs"]["top_p"] = config.top_p

        import pdb; pdb.set_trace()
        if config.stream:
            from langchain.callbacks.streaming_stdout import \
                StreamingStdOutCallbackHandler

            callbacks = [StreamingStdOutCallbackHandler()]
            chat = BedrockChat(**kwargs, streaming=config.stream, callbacks=callbacks)
        else:
            chat = BedrockChat(**kwargs)
        
        return chat(messages).content
