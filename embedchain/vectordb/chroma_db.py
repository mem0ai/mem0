import logging
from typing import Any, Dict, List, Optional

from langchain.docstore.document import Document

from embedchain.config import ChromaDbConfig
from embedchain.helper_classes.json_serializable import register_deserializable
from embedchain.vectordb.base_vector_db import BaseVectorDB

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
        if config:
            self.config = config
        else:
            self.config = ChromaDbConfig()

        self.settings = Settings()
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
            raise ValueError("Embedder not set. Please set an embedder with `set_embedder` before initialization.")
        self._get_or_create_collection(self.config.collection_name)

    def _get_or_create_db(self):
        """Get or create the database."""
        return self.client

    def _get_or_create_collection(self, name):
        """Get or create the collection."""
        if not hasattr(self, "embedder") or not self.embedder:
            raise ValueError("Cannot create a Chroma database collection without an embedder.")
        self.collection = self.client.get_or_create_collection(
            name=name,
            embedding_function=self.embedder.embedding_fn,
        )
        return self.collection

    def get(self, ids: List[str], where: Dict[str, any]) -> List[str]:
        """
        Get existing doc ids present in vector database
        :param ids: list of doc ids to check for existance
        :param where: Optional. to filter data
        """
        existing_docs = self.collection.get(
            ids=ids,
            where=where,  # optional filter
        )

        return set(existing_docs["ids"])

    def add(self, documents: List[str], metadatas: List[object], ids: List[str]) -> Any:
        """
        add data in vector database
        :param documents: list of texts to add
        :param metadatas: list of metadata associated with docs
        :param ids: ids of docs
        """
        self.collection.add(documents=documents, metadatas=metadatas, ids=ids)

    def _format_result(self, results):
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
        query contents from vector data base based on vector similarity
        :param input_query: list of query string
        :param n_results: no of similar documents to fetch from database
        :param where: Optional. to filter data
        :return: The content of the document that matched your query.
        """
        try:
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
        self.config.collection_name = name
        self._get_or_create_collection(self.config.collection_name)

    def count(self) -> int:
        """
        Count the number of embeddings.

        :return: The number of embeddings.
        """
        return self.collection.count()

    def reset(self):
        """
        Resets the database. Deletes all embeddings irreversibly.
        `App` does not have to be reinitialized after using this method.
        """
        # Delete all data from the database
        try:
            self.client.reset()
        except ValueError:
            raise ValueError(
                "For safety reasons, resetting is disabled."
                'Please enable it by including `chromadb_settings={"allow_reset": True}` in your ChromaDbConfig'
            ) from None
        # Recreate
        self._get_or_create_collection(self.config.collection_name)

        # Todo: Automatically recreating a collection with the same name cannot be the best way to handle a reset.
        # A downside of this implementation is, if you have two instances,
        # the other instance will not get the updated `self.collection` attribute.
        # A better way would be to create the collection if it is called again after being reset.
        # That means, checking if collection exists in the db-consuming methods, and creating it if it doesn't.
        # That's an extra steps for all uses, just to satisfy a niche use case in a niche method. For now, this will do.
