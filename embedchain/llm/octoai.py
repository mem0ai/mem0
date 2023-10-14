import os
from typing import Optional

from langchain.llms.octoai_endpoint import OctoAIEndpoint

from embedchain.config import BaseLlmConfig
from embedchain.helper.json_serializable import register_deserializable
from embedchain.llm.base import BaseLlm

@register_deserializable
class OctoaiLlm(BaseLlm):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        if "OCTOAI_API_TOKEN" not in os.environ:
            raise ValueError("Please set the OCTOAI_API_TOKEN environment variable.")
        if "ENDPOINT_URL" not in os.environ:
            raise ValueError ("Please enter your model's endpoint url")

        # Set default config values specific to this llm
        if not config:
            config = BaseLlmConfig()
            # Add variables to this block that have a default value in the parent class
            config.max_tokens = 200
            config.temperature = 0.75
            config.top_p = 0.95
    

        super().__init__(config=config)

    def get_llm_model_answer(self, prompt):
        # TODO: Move the model and other inputs into config
        if self.config.system_prompt:
             OctoAIEndpoint(
                octoai_api_token=os.environ["OCTOAI_API_TOKEN"],
                endpoint_url="https://llama-2-7b-chat-demo-kk0powt97tmb.octoai.run/v1/chat/completions",
                model_kwargs={
                    "model": "llama-2-7b-chat",
                    "messages": [
                        {
                            "role": "system",
                            "content": prompt
                        }
                    ],
                    "stream": False,
                    "max_tokens": 256
                            }
            )
        
        llm = OctoAIEndpoint(octoai_api_token= os.environ["OCTOAI_API_TOKEN"], 
                             endpoint_url = os.environ["ENDPOINT_URL"],
            model_kwargs={
                "max_new_tokens": self.config.max_tokens,
                "temperature": self.config.temperature,
                "top_p": self.config.top_p,
                "repetition_penalty": 1,
                "seed": None,
                "stop": [],
            },
        )
        return llm(prompt)