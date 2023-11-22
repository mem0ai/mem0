import logging
from typing import Any, Dict, List, Optional, Tuple, Union

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
    from embedchain.utils import use_pysqlite3

    use_pysqlite3()
    import chromadb
    from chromadb.config import Settings
    from chromadb.errors import InvalidDimensionException


@register_deserializable
class ChromaDB(BaseVectorDB):
    """Vector database using ChromaDB."""

    BATCH_SIZE = 100

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

    def _generate_where_clause(self, where: Dict[str, any]) -> str:
        # If only one filter is supplied, return it as is
        # (no need to wrap in $and based on chroma docs)
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
            args["where"] = self._generate_where_clause(where)
        if limit:
            args["limit"] = limit
        return self.collection.get(**args)

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
        size = len(documents)
        if skip_embedding and (embeddings is None or len(embeddings) != len(documents)):
            raise ValueError("Cannot add documents to chromadb with inconsistent embeddings")

        if len(documents) != size or len(metadatas) != size or len(ids) != size:
            raise ValueError(
                "Cannot add documents to chromadb with inconsistent sizes. Documents size: {}, Metadata size: {},"
                " Ids size: {}".format(len(documents), len(metadatas), len(ids))
            )

        for i in tqdm(range(0, len(documents), self.BATCH_SIZE), desc="Inserting batches in chromadb"):
            if skip_embedding:
                self.collection.add(
                    embeddings=embeddings[i : i + self.BATCH_SIZE],
                    documents=documents[i : i + self.BATCH_SIZE],
                    metadatas=metadatas[i : i + self.BATCH_SIZE],
                    ids=ids[i : i + self.BATCH_SIZE],
                )
            else:
                self.collection.add(
                    documents=documents[i : i + self.BATCH_SIZE],
                    metadatas=metadatas[i : i + self.BATCH_SIZE],
                    ids=ids[i : i + self.BATCH_SIZE],
                )

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

    def query(
        self,
        input_query: List[str],
        n_results: int,
        where: Dict[str, any],
        skip_embedding: bool,
        citations: bool = False,
    ) -> Union[List[Tuple[str, str, str]], List[str]]:
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
        :param citations: we use citations boolean param to return context along with the answer.
        :type citations: bool, default is False.
        :raises InvalidDimensionException: Dimensions do not match.
        :return: The content of the document that matched your query,
        along with url of the source and doc_id (if citations flag is true)
        :rtype: List[str], if citations=False, otherwise List[Tuple[str, str, str]]
        """
        try:
            if skip_embedding:
                result = self.collection.query(
                    query_embeddings=[
                        input_query,
                    ],
                    n_results=n_results,
                    where=self._generate_where_clause(where),
                )
            else:
                result = self.collection.query(
                    query_texts=[
                        input_query,
                    ],
                    n_results=n_results,
                    where=self._generate_where_clause(where),
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
                source = metadata["url"]
                doc_id = metadata["doc_id"]
                contexts.append((context, source, doc_id))
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
