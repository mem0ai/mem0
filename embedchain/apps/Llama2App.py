from typing import Optional

from embedchain.apps.CustomApp import CustomApp
from embedchain.config import CustomAppConfig
from embedchain.embedder.openai_embedder import OpenAiEmbedder
from embedchain.helper_classes.json_serializable import register_deserializable
from embedchain.llm.llama2_llm import Llama2Llm
from embedchain.vectordb.chroma_db import ChromaDB


@register_deserializable
class Llama2App(CustomApp):
    """
    The EmbedChain Llama2App class.
    Has two functions: add and query.

    adds(data_type, url): adds the data from the given URL to the vector db.
    query(query): finds answer to the given query using vector database and LLM.
    """

    def __init__(self, config: CustomAppConfig = None, system_prompt: Optional[str] = None):
        """
        :param config: CustomAppConfig instance to load as configuration. Optional.
        :param system_prompt: System prompt string. Optional.
        """

        if config is None:
            config = CustomAppConfig()

        super().__init__(
            config=config, llm=Llama2Llm(), db=ChromaDB(), embedder=OpenAiEmbedder(), system_prompt=system_prompt
        )
