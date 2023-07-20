import os

from langchain.llms import Replicate

from embedchain.config import AppConfig
from embedchain.embedchain import EmbedChain


class Llama2App(EmbedChain):
    """
    The EmbedChain Llama2App class.
    Has two functions: add and query.

    adds(data_type, url): adds the data from the given URL to the vector db.
    query(query): finds answer to the given query using vector database and LLM.
    """

    def __init__(self, config: AppConfig = None):
        """
        :param config: AppConfig instance to load as configuration. Optional.
        """
        if "REPLICATE_API_TOKEN" not in os.environ:
            raise ValueError("Please set the REPLICATE_API_TOKEN environment variable.")

        if config is None:
            config = AppConfig()

        super().__init__(config)

    def get_llm_model_answer(self, prompt, config: AppConfig = None):
        # TODO: Move the model and other inputs into config
        llm = Replicate(
            model="a16z-infra/llama13b-v2-chat:df7690f1994d94e96ad9d568eac121aecf50684a0b0963b25a41cc40061269e5",
            input={"temperature": 0.75, "max_length": 500, "top_p": 1},
        )
        return llm(prompt)
