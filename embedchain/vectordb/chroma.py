import logging
from typing import Any, Optional, Union

from chromadb import Collection, QueryResult
from langchain.docstore.document import Document
from tqdm import tqdm

from embedchain.config import ChromaDbConfig
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.vectordb.base import BaseVectorDB

try:
    import chromadb
    from chromadb.config import Settings
    from chromadb.errors import InvalidDimensionException
except RuntimeError:
    from embedchain.utils.misc import use_pysqlite3

    use_pysqlite3()
    import chromadb
    from chromadb.config import Settings
    from chromadb.errors import InvalidDimensionException


logger = logging.getLogger(__name__)


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

        self.settings = Settings(anonymized_telemetry=False)
        self.settings.allow_reset = self.config.allow_reset if hasattr(self.config, "allow_reset") else False
        self.batch_size = self.config.batch_size
        if self.config.chroma_settings:
            for key, value in self.config.chroma_settings.items():
                if hasattr(self.settings, key):
                    setattr(self.settings, key, value)

        if self.config.host and self.config.port:
            logger.info(f"Connecting to ChromaDB server: {self.config.host}:{self.config.port}")
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

    @staticmethod
    def _generate_where_clause(where: dict[str, any]) -> dict[str, any]:
        # If only one filter is supplied, return it as is
        # (no need to wrap in $and based on chroma docs)
        if where is None:
            return {}
        if len(where.keys()) <= 1:
            return where
        where_filters = []
        for k, v in where.items():
            if isinstance(v, str):
                where_filters.append({k: v})
        return {"$and": where_filters}

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

    def get(self, ids: Optional[list[str]] = None, where: Optional[dict[str, any]] = None, limit: Optional[int] = None):
        """
        Get existing doc ids present in vector database

        :param ids: list of doc ids to check for existence
        :type ids: list[str]
        :param where: Optional. to filter data
        :type where: dict[str, Any]
        :param limit: Optional. maximum number of documents
        :type limit: Optional[int]
        :return: Existing documents.
        :rtype: list[str]
        """
        args = {}
        if ids:
            args["ids"] = ids
        if where:
            args["where"] = self._generate_where_clause(where)
        if limit:
            args["limit"] = limit
        return self.collection.get(**args)

    def add(
        self,
        documents: list[str],
        metadatas: list[object],
        ids: list[str],
        **kwargs: Optional[dict[str, Any]],
    ) -> Any:
        """
        Add vectors to chroma database

        :param documents: Documents
        :type documents: list[str]
        :param metadatas: Metadatas
        :type metadatas: list[object]
        :param ids: ids
        :type ids: list[str]
        """
        size = len(documents)
        if len(documents) != size or len(metadatas) != size or len(ids) != size:
            raise ValueError(
                "Cannot add documents to chromadb with inconsistent sizes. Documents size: {}, Metadata size: {},"
                " Ids size: {}".format(len(documents), len(metadatas), len(ids))
            )

        for i in tqdm(range(0, len(documents), self.batch_size), desc="Inserting batches in chromadb"):
            self.collection.add(
                documents=documents[i : i + self.batch_size],
                metadatas=metadatas[i : i + self.batch_size],
                ids=ids[i : i + self.batch_size],
            )
        self.config

    @staticmethod
    def _format_result(results: QueryResult) -> list[tuple[Document, float]]:
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

    def query(
        self,
        input_query: str,
        n_results: int,
        where: Optional[dict[str, any]] = None,
        raw_filter: Optional[dict[str, any]] = None,
        citations: bool = False,
        **kwargs: Optional[dict[str, any]],
    ) -> Union[list[tuple[str, dict]], list[str]]:
        """
        Query contents from vector database based on vector similarity

        :param input_query: query string
        :type input_query: str
        :param n_results: no of similar documents to fetch from database
        :type n_results: int
        :param where: to filter data
        :type where: dict[str, Any]
        :param raw_filter: Raw filter to apply
        :type raw_filter: dict[str, Any]
        :param citations: we use citations boolean param to return context along with the answer.
        :type citations: bool, default is False.
        :raises InvalidDimensionException: Dimensions do not match.
        :return: The content of the document that matched your query,
        along with url of the source and doc_id (if citations flag is true)
        :rtype: list[str], if citations=False, otherwise list[tuple[str, str, str]]
        """
        if where and raw_filter:
            raise ValueError("Both `where` and `raw_filter` cannot be used together.")

        where_clause = {}
        if raw_filter:
            where_clause = raw_filter
        if where:
            where_clause = self._generate_where_clause(where)
        try:
            result = self.collection.query(
                query_texts=[
                    input_query,
                ],
                n_results=n_results,
                where=where_clause,
            )
        except InvalidDimensionException as e:
            raise InvalidDimensionException(
                e.message()
                + ". This is commonly a side-effect when an embedding function, different from the one used to add the"
                " embeddings, is used to retrieve an embedding from the database."
            ) from None
        results_formatted = self._format_result(result)
        contexts = []
        for result in results_formatted:
            context = result[0].page_content
            if citations:
                metadata = result[0].metadata
                metadata["score"] = result[1]
                contexts.append((context, metadata))
            else:
                contexts.append(context)
        return contexts

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
        return self.collection.delete(where=self._generate_where_clause(where))

    def reset(self):
        """
        Resets the database. Deletes all embeddings irreversibly.
        """
        # Delete all data from the collection
        try:
            self.client.delete_collection(self.config.collection_name)
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
