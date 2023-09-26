from typing import Optional

from embedchain.config import CustomAppConfig
from embedchain.embedchain import EmbedChain
from embedchain.embedder.base import BaseEmbedder
from embedchain.helper.json_serializable import register_deserializable
from embedchain.llm.base import BaseLlm
from embedchain.vectordb.base import BaseVectorDB


@register_deserializable
class CustomApp(EmbedChain):
    """
    Embedchain's custom app allows for most flexibility.

    You can craft your own mix of various LLMs, vector databases and embedding model/functions.

    Methods:
    add(source, data_type): adds the data from the given URL to the vector db.
    query(query): finds answer to the given query using vector database and LLM.
    chat(query): finds answer to the given query using vector database and LLM, with conversation history.
    """

    def __init__(
        self,
        config: Optional[CustomAppConfig] = None,
        llm: BaseLlm = None,
        db: BaseVectorDB = None,
        embedder: BaseEmbedder = None,
        system_prompt: Optional[str] = None,
    ):
        """
        Initialize a new `CustomApp` instance. You have to choose a LLM, database and embedder.

        :param config: Config for the app instance. This is the most basic configuration,
        that does not fall into the LLM, database or embedder category, defaults to None
        :type config: Optional[CustomAppConfig], optional
        :param llm: LLM Class instance. example: `from embedchain.llm.openai import OpenAILlm`, defaults to None
        :type llm: BaseLlm
        :param db: The database to use for storing and retrieving embeddings,
        example: `from embedchain.vectordb.chroma_db import ChromaDb`, defaults to None
        :type db: BaseVectorDB
        :param embedder: The embedder (embedding model and function) use to calculate embeddings.
        example: `from embedchain.embedder.gpt4all_embedder import GPT4AllEmbedder`, defaults to None
        :type embedder: BaseEmbedder
        :param system_prompt: System prompt that will be provided to the LLM as such, defaults to None
        :type system_prompt: Optional[str], optional
        :raises ValueError: LLM, database or embedder has not been defined.
        :raises TypeError: LLM, database or embedder is not a valid class instance.
        """
        # Config is not required, it has a default
        if config is None:
            config = CustomAppConfig()

        if llm is None:
            raise ValueError("LLM must be provided for custom app. Please import from `embedchain.llm`.")
        if db is None:
            raise ValueError("Database must be provided for custom app. Please import from `embedchain.vectordb`.")
        if embedder is None:
            raise ValueError("Embedder must be provided for custom app. Please import from `embedchain.embedder`.")

        if not isinstance(config, CustomAppConfig):
            raise TypeError(
                "Config is not a `CustomAppConfig` instance. "
                "Please make sure the type is right and that you are passing an instance."
            )
        if not isinstance(llm, BaseLlm):
            raise TypeError(
                "LLM is not a `BaseLlm` instance. "
                "Please make sure the type is right and that you are passing an instance."
            )
        if not isinstance(db, BaseVectorDB):
            raise TypeError(
                "Database is not a `BaseVectorDB` instance. "
                "Please make sure the type is right and that you are passing an instance."
            )
        if not isinstance(embedder, BaseEmbedder):
            raise TypeError(
                "Embedder is not a `BaseEmbedder` instance. "
                "Please make sure the type is right and that you are passing an instance."
            )

        super().__init__(config=config, llm=llm, db=db, embedder=embedder, system_prompt=system_prompt)
