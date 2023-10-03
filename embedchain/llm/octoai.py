import os
from typing import Optional

from langchain.llms.octoai_endpoint import OctoAIEndpoint

from embedchain.config import BaseLlmConfig
from embedchain.helper.json_serializable import register_deserializable
from embedchain.llm.base import BaseLlm

"""
import os

os.environ["OCTOAI_API_TOKEN"] = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6IjNkMjMzOTQ5In0.eyJzdWIiOiJhMjllYTQzMC1mYTY2LTRjNGEtYWE4Ny0wOWU2NWEyM2FmNGIiLCJ0eXBlIjoidXNlckFjY2Vzc1Rva2VuIiwidGVuYW50SWQiOiJiOWU2ZjY1Zi0wZDg3LTRhYzQtODcxYS0xN2JjNTM1MzlkMmEiLCJ1c2VySWQiOiI2ZTM2ZTM0MS03YjIxLTQ4M2MtYmZmMi0zMDRiY2I2MDMyYzIiLCJyb2xlcyI6WyJGRVRDSC1ST0xFUy1CWS1BUEkiXSwicGVybWlzc2lvbnMiOlsiRkVUQ0gtUEVSTUlTU0lPTlMtQlktQVBJIl0sImF1ZCI6IjNkMjMzOTQ5LWEyZmItNGFiMC1iN2VjLTQ2ZjYyNTVjNTEwZSIsImlzcyI6Imh0dHBzOi8vaWRlbnRpdHkub2N0b21sLmFpIiwiaWF0IjoxNjk1ODYxNjI4fQ.Fef2ZGqKwSmEjHWxtcZaaWJJrRodT-z_UVkcDKRIfjOoGj08PuUQdNk5N9PnpvJgwzfYjJcP2vXUmpNATCN8Wjmn3Nm6Er8MFewHhpdkraWmLfJ6Tgib8aOEKZQ53n45C_-LWMCL2D7u0UZzi5rmQ_UD-puPKRYYDX5LHIBCFqxgtO5dvXvT_ef_H55v3hq4qB6wh5TLN65EznI3OOSuRyo7sLxiVusCB7t__JAC7WaKxJacBY2h6AeTKbEYX4X3zzlyQRryQhC9Bq80UeuGwVOzI25SmK9UXKHv8NKiTwzTux2d6Xy0l-r4EhhnSAF81qicTmAiQiXqyWo_V8b67w"
os.environ["ENDPOINT_URL"] = "https://llama-2-7b-chat-demo-kk0powt97tmb.octoai.run/v1/chat/completions"

from langchain.llms.octoai_endpoint import OctoAIEndpoint


llm = OctoAIEndpoint(
    model_kwargs={
        "max_new_tokens": 200,
        "temperature": 0.75,
        "top_p": 0.95,
        "seed": None,
        "stop": [],
    },
)

question = "Who was leonardo davinci?"

llm(question)
"""


@register_deserializable
class OctoAILlm(BaseLlm):
    def __init__(self, config: Optional[BaseLlmConfig] = None):
        if "OCTOAI_API_TOKEN" not in os.environ:
            raise ValueError("Please set the OCTOAI_API_TOKEN environment variable.")

        # Set default config values specific to this llm
        if not config:
            config = BaseLlmConfig()
            # Add variables to this block that have a default value in the parent class
            config.max_tokens = 200
            config.temperature = 0.75
            config.top_p = 0.95
            config.repetition_penalty = 1

        # Add variables that are `none` by default to this block.
        if not config.endpoint_url:
            config.endpoint_url = "https://mpt-7b-demo-kk0powt97tmb.octoai.run/generate_stream"

        super().__init__(config=config)

    def get_llm_model_answer(self, prompt):
        # TODO: Move the model and other inputs into config
        if self.config.system_prompt:
            raise ValueError("OctoAIApp does not support `system_prompt`")
        llm = OctoAIEndpoint(
            model_kwargs={
                "max_new_tokens": self.config.max_tokens,
                "temperature": self.config.temperature,
                "top_p": self.config.top_p,
                "repetition_penalty": self.config.repetition_penalty,
            },
        )
        return llm(prompt)
