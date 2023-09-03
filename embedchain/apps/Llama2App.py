import os

from langchain.llms import Replicate

from embedchain.config import AppConfig, BaseLlmConfig, CustomAppConfig
from embedchain.apps.CustomApp import CustomApp
from embedchain.llm.llama2_llm import Llama2Llm
from embedchain.vectordb.chroma_db import ChromaDB
from embedchain.embedder.openai_embedder import OpenAiEmbedder


class Llama2App(CustomApp):
    """
    The EmbedChain Llama2App class.
    Has two functions: add and query.

    adds(data_type, url): adds the data from the given URL to the vector db.
    query(query): finds answer to the given query using vector database and LLM.
    """

    def __init__(self, config: CustomAppConfig = None):
        """
        :param config: AppConfig instance to load as configuration. Optional.
        """

        if config is None:
            config = AppConfig()

        super().__init__(config=config, llm=Llama2Llm(), db=ChromaDB(), embedder=OpenAiEmbedder())

