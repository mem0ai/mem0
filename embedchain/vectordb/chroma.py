import logging
from typing import Any, Dict, List, Optional

from chromadb import Collection, QueryResult
from langchain.docstore.document import Document

from embedchain.config import ChromaDbConfig
from embedchain.helper.json_serializable import register_deserializable
from embedchain.vectordb.base import BaseVectorDB

try:
    import chromadb
    from chromadb.config import Settings
    from chromadb.errors import InvalidDimensionException
except RuntimeError:
    from embedchain.utils import use_pysqlite3

    use_pysqlite3()
    import chromadb
    from chromadb.config import Settings
    from chromadb.errors import InvalidDimensionException


@register_deserializable
class ChromaDB(BaseVectorDB):
    """Vector database using ChromaDB."""

    def __init__(self, config: Optional[ChromaDbConfig] = None):
        """Initialize a new ChromaDB instance

        :param config: Configuration options for Chroma, defaults to None
        :type config: Optional[ChromaDbConfig], optional
        """
        if config:
            self.config = config
        else:
            self.config = ChromaDbConfig()

        self.settings = Settings()
        self.settings.allow_reset = self.config.allow_reset
        if self.config.chroma_settings:
            for key, value in self.config.chroma_settings.items():
                if hasattr(self.settings, key):
                    setattr(self.settings, key, value)

        if self.config.host and self.config.port:
            logging.info(f"Connecting to ChromaDB server: {self.config.host}:{self.config.port}")
            self.settings.chroma_server_host = self.config.host
            self.settings.chroma_server_http_port = self.config.port
            self.settings.chroma_api_impl = "chromadb.api.fastapi.FastAPI"
        else:
            if self.config.dir is None:
                self.config.dir = "db"

            self.settings.persist_directory = self.config.dir
            self.settings.is_persistent = True

        self.client = chromadb.Client(self.settings)
        super().__init__(config=self.config)

    def _initialize(self):
        """
        This method is needed because `embedder` attribute needs to be set externally before it can be initialized.
        """
        if not self.embedder:
            raise ValueError(
                "Embedder not set. Please set an embedder with `_set_embedder()` function before initialization."
            )
        self._get_or_create_collection(self.config.collection_name)

    def _get_or_create_db(self):
        """Called during initialization"""
        return self.client

    def _get_or_create_collection(self, name: str) -> Collection:
        """
        Get or create a named collection.

        :param name: Name of the collection
        :type name: str
        :raises ValueError: No embedder configured.
        :return: Created collection
        :rtype: Collection
        """
        if not hasattr(self, "embedder") or not self.embedder:
            raise ValueError("Cannot create a Chroma database collection without an embedder.")
        self.collection = self.client.get_or_create_collection(
            name=name,
            embedding_function=self.embedder.embedding_fn,
        )
        return self.collection

    def get(self, ids: Optional[List[str]] = None, where: Optional[Dict[str, any]] = None, limit: Optional[int] = None):
        """
        Get existing doc ids present in vector database

        :param ids: list of doc ids to check for existence
        :type ids: List[str]
        :param where: Optional. to filter data
        :type where: Dict[str, Any]
        :param limit: Optional. maximum number of documents
        :type limit: Optional[int]
        :return: Existing documents.
        :rtype: List[str]
        """
        args = {}
        if ids:
            args["ids"] = ids
        if where:
            args["where"] = where
        if limit:
            args["limit"] = limit
        return self.collection.get(**args)

    def get_advanced(self, where):
        return self.collection.get(where=where, limit=1)

    def add(
        self,
        embeddings: List[List[float]],
        documents: List[str],
        metadatas: List[object],
        ids: List[str],
        skip_embedding: bool,
    ) -> Any:
        """
        Add vectors to chroma database

        :param embeddings: list of embeddings to add
        :type embeddings: List[List[str]]
        :param documents: Documents
        :type documents: List[str]
        :param metadatas: Metadatas
        :type metadatas: List[object]
        :param ids: ids
        :type ids: List[str]
        :param skip_embedding: Optional. If True, then the embeddings are assumed to be already generated.
        :type skip_embedding: bool
        """
        if skip_embedding:
            self.collection.add(embeddings=embeddings, documents=documents, metadatas=metadatas, ids=ids)
        else:
            self.collection.add(documents=documents, metadatas=metadatas, ids=ids)

    def _format_result(self, results: QueryResult) -> list[tuple[Document, float]]:
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

    def query(self, input_query: List[str], n_results: int, where: Dict[str, any], skip_embedding: bool) -> List[str]:
        """
        Query contents from vector database based on vector similarity

        :param input_query: list of query string
        :type input_query: List[str]
        :param n_results: no of similar documents to fetch from database
        :type n_results: int
        :param where: to filter data
        :type where: Dict[str, Any]
        :param skip_embedding: Optional. If True, then the input_query is assumed to be already embedded.
        :type skip_embedding: bool
        :raises InvalidDimensionException: Dimensions do not match.
        :return: The content of the document that matched your query.
        :rtype: List[str]
        """
        try:
            if skip_embedding:
                result = self.collection.query(
                    query_embeddings=[
                        input_query,
                    ],
                    n_results=n_results,
                    where=where,
                )
            else:
                result = self.collection.query(
                    query_texts=[
                        input_query,
                    ],
                    n_results=n_results,
                    where=where,
                )
        except InvalidDimensionException as e:
            raise InvalidDimensionException(
                e.message()
                + ". This is commonly a side-effect when an embedding function, different from the one used to add the embeddings, is used to retrieve an embedding from the database."  # noqa E501
            ) from None
        results_formatted = self._format_result(result)
        contents = [result[0].page_content for result in results_formatted]
        return contents

    def set_collection_name(self, name: str):
        """
        Set the name of the collection. A collection is an isolated space for vectors.

        :param name: Name of the collection.
        :type name: str
        """
        if not isinstance(name, str):
            raise TypeError("Collection name must be a string")
        self.config.collection_name = name
        self._get_or_create_collection(self.config.collection_name)

    def count(self) -> int:
        """
        Count number of documents/chunks embedded in the database.

        :return: number of documents
        :rtype: int
        """
        return self.collection.count()

    def delete(self, where):
        return self.collection.delete(where=where)

    def reset(self):
        """
        Resets the database. Deletes all embeddings irreversibly.
        """
        # Delete all data from the database
        try:
            self.client.reset()
        except ValueError:
            raise ValueError(
                "For safety reasons, resetting is disabled. "
                "Please enable it by setting `allow_reset=True` in your ChromaDbConfig"
            ) from None
        # Recreate
        self._get_or_create_collection(self.config.collection_name)

        # Todo: Automatically recreating a collection with the same name cannot be the best way to handle a reset.
        # A downside of this implementation is, if you have two instances,
        # the other instance will not get the updated `self.collection` attribute.
        # A better way would be to create the collection if it is called again after being reset.
        # That means, checking if collection exists in the db-consuming methods, and creating it if it doesn't.
        # That's an extra steps for all uses, just to satisfy a niche use case in a niche method. For now, this will do.
