import logging
from typing import Any

from chromadb.api.types import Documents, Embeddings
from dotenv import load_dotenv

from embedchain.models import EmbeddingFunctions, LlmModels

from .BaseAppConfig import BaseAppConfig

load_dotenv()


class CustomAppConfig(BaseAppConfig):
    """
    Config to initialize an embedchain custom `App` instance, with extra config options.
    """

    def __init__(
        self,
        log_level=None,
        embedding_fn: EmbeddingFunctions = None,
        db=None,
        host=None,
        port=None,
        id=None,
        llm_model: LlmModels = None,
    ):
        """
        :param log_level: Optional. (String) Debug level
        ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'].
        :param embedding_fn: Optional. Embedding function to use.
        :param db: Optional. (Vector) database to use for embeddings.
        :param id: Optional. ID of the app. Document metadata will have this id.
        :param host: Optional. Hostname for the database server.
        :param port: Optional. Port for the database server.
        :param llm_model: Optional. (LlmModels): Llm Model to use.
        """
        if llm_model:
            self.llm_model = llm_model
        else:
            raise ValueError("CustomApp must have a llm_model assigned.")

        super().__init__(
            log_level=log_level,
            ef=CustomAppConfig.embedding_function(embedding_function=embedding_fn),
            db=db,
            host=host,
            port=port,
            id=id,
        )

    @staticmethod
    def langchain_default_concept(embeddings: Any):
        """
        Langchains default function layout for embeddings.
        """

        def embed_function(texts: Documents) -> Embeddings:
            return embeddings.embed_documents(texts)

        return embed_function

    @staticmethod
    def embedding_function(embedding_function: EmbeddingFunctions):
        if not isinstance(embedding_function, EmbeddingFunctions):
            raise ValueError(
                f"Invalid option: '{embedding_function}'. Expecting one of the following options: {list(map(lambda x: x.value, EmbeddingFunctions))}"  # noqa: E501
            )

        if embedding_function == EmbeddingFunctions.OPENAI:
            from langchain.embeddings import OpenAIEmbeddings

            embeddings = OpenAIEmbeddings()
            return CustomAppConfig.langchain_default_concept(embeddings)

        elif embedding_function == EmbeddingFunctions.HUGGING_FACE:
            from langchain.embeddings import HuggingFaceEmbeddings

            embeddings = HuggingFaceEmbeddings()
            return CustomAppConfig.langchain_default_concept(embeddings)

        elif embedding_function == EmbeddingFunctions.VERTEX_AI:
            from langchain.embeddings import VertexAIEmbeddings

            embeddings = VertexAIEmbeddings()
            return CustomAppConfig.langchain_default_concept(embeddings)
