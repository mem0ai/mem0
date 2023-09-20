import os
import logging
from typing import Dict, List, Optional

from weaviate import AuthApiKey, Client
from langchain.docstore.document import Document

from embedchain.config import WeaviateDbConfig
from embedchain.helper.json_serializable import register_deserializable
from embedchain.vectordb.base_vector_db import BaseVectorDB


@register_deserializable
class Weaviate(BaseVectorDB):
    """Vector database using Weaviate."""

    def __init__(self, weaviate_api_key, cluster_url, config: Optional[WeaviateDbConfig] = None):
        """Initialize a new Weaviate instance

        :param weaviate_api_key: Weaviate API key to authenticate
        :type weaviate_api_key: str
        :param cluster_url: Weaviate cluster URL for connection
        :type cluster_url: str
        :param config: Configuration options for Weaviate, defaults to None
        :type config: Optional[WeaviateDbConfig], optional
        """
        if config:
            self.config = config
        else:
            self.config = WeaviateDbConfig()

        self.allow_reset = self.config.allow_reset
        self.client = Client(
            url=cluster_url,
            auth_client_secret=AuthApiKey(api_key=weaviate_api_key),
            additional_headers={
                "X-OpenAI-Api-Key": os.environ["OPENAI_API_KEY"],
            },
        )

        super().__init__(config=self.config)

    def _initialize(self):
        """
        This method is needed because `embedder` attribute needs to be set externally before it can be initialized.
        """
        if not self.embedder:
            raise ValueError("Embedder not set. Please set an embedder with `set_embedder` before initialization.")
        self._get_or_create_class(self.config.class_name)

    def _get_or_create_db(self):
        """Called during initialization"""
        return self.client

    def _get_or_create_class(self, name: str):
        """
        Get or create a named class.

        :param name: Name of the class
        :type name: str
        :raises ValueError: No embedder configured.
        """
        if not hasattr(self, "embedder") or not self.embedder:
            raise ValueError("Cannot create a Weaviate database class without an embedder.")
        try:
            self.client.schema.get(name)
            logging.debug(f"Class already exists with name : {name}")
        except:
            self.client.schema.create_class(dict(self.config))

    def get(self, ids: List[str], where: Dict[str, any]) -> List[str]:
        """
        Get existing doc ids present in vector database

        :param ids: list of doc ids to check for existence
        :type ids: List[str]
        :param where: Optional. to filter data
        :type where: Dict[str, any]
        :return: Existing documents.
        :rtype: List[str]
        """
        pass

    def add(self, documents: List[str], metadatas: List[object], ids: List[str]):
        """
        Add vectors to weaviate database

        :param documents: Documents
        :type documents: List[str]
        :param metadatas: Metadatas
        :type metadatas: List[object]
        :param ids: ids
        :type ids: List[str]
        """
        pass

    def _format_result(self, results) -> list[tuple[Document, float]]:
        """
        Format Chroma results

        :param results: ChromaDB query results to format.
        :type results: QueryResult
        :return: Formatted results
        :rtype: list[tuple[Document, float]]
        """
        return [
            (Document(page_content=result[0], metadata=result[1] or {}), result[2])
            for result in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            )
        ]

    def query(self, input_query: List[str], n_results: int, where: Dict[str, any]) -> List[str]:
        """
        Query contents from vector data base based on vector similarity

        :param input_query: list of query string
        :type input_query: List[str]
        :param n_results: no of similar documents to fetch from database
        :type n_results: int
        :param where: to filter data
        :type where: Dict[str, any]
        :raises InvalidDimensionException: Dimensions do not match.
        :return: The content of the document that matched your query.
        :rtype: List[str]
        """
        pass

    def set_class_name(self, name: str):
        """
        Set the name of the class. A collection is an isolated space for vectors.

        :param name: Name of the class.
        :type name: str
        """
        self.config.class_name = name
        self._get_or_create_collection(self.config.class_name)

    def count(self) -> int:
        """
        Count number of documents/chunks embedded in the database.

        :return: number of documents
        :rtype: int
        """
        return self.client.query.aggregate(self.config.class_name).with_meta_count()

    def reset(self):
        """
        Resets the database. Deletes all embeddings irreversibly.
        """
        # Delete all data from the database
        if self.allow_reset:
            self.client.schema.delete_class(self.config.class_name)
        else:
            raise ValueError(
                "For safety reasons, resetting is disabled."
                "Please enable it by setting `allow_reset=True` in your WeaviateDbConfig"
            ) from None
        # Recreate
        self._get_or_create_class(self.config.class_name)

        # Todo: Automatically recreating a collection with the same name cannot be the best way to handle a reset.
        # A downside of this implementation is, if you have two instances,
        # the other instance will not get the updated `self.collection` attribute.
        # A better way would be to create the collection if it is called again after being reset.
        # That means, checking if collection exists in the db-consuming methods, and creating it if it doesn't.
        # That's an extra steps for all uses, just to satisfy a niche use case in a niche method. For now, this will do.
