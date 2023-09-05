import os
from typing import Optional

from langchain.llms import Replicate

from embedchain.config import BaseLlmConfig
from embedchain.helper_classes.json_serializable import register_deserializable
from embedchain.llm.base_llm import BaseLlm


@register_deserializable
class Llama2Llm(BaseLlm):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        if "REPLICATE_API_TOKEN" not in os.environ:
            raise ValueError("Please set the REPLICATE_API_TOKEN environment variable.")
        super().__init__(config=config)

    def get_llm_model_answer(self, prompt):
        # TODO: Move the model and other inputs into config
        if self.config.system_prompt:
            raise ValueError("Llama2App does not support `system_prompt`")
        llm = Replicate(
            model="a16z-infra/llama13b-v2-chat:df7690f1994d94e96ad9d568eac121aecf50684a0b0963b25a41cc40061269e5",
            input={"temperature": self.config.temperature or 0.75, "max_length": 500, "top_p": self.config.top_p},
        )
        return llm(prompt)
