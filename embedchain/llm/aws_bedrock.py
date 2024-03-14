import os
from typing import Optional

from langchain_community.llms import Bedrock

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

        self.boto_client = boto3.client("bedrock-runtime", "us-west-2" or os.environ.get("AWS_REGION"))

        kwargs = {
            "model_id": config.model or "amazon.titan-text-express-v1",
            "client": self.boto_client,
            "model_kwargs": config.model_kwargs
            or {
                "temperature": config.temperature,
            },
        }

        if config.stream:
            from langchain.callbacks.streaming_stdout import \
                StreamingStdOutCallbackHandler

            callbacks = [StreamingStdOutCallbackHandler()]
            llm = Bedrock(**kwargs, streaming=config.stream, callbacks=callbacks)
        else:
            llm = Bedrock(**kwargs)

        return llm.invoke(prompt)
