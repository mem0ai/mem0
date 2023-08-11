import logging
from typing import Any, Dict, List

from chromadb.errors import InvalidDimensionException
from langchain.docstore.document import Document

try:
    import chromadb
except RuntimeError:
    from embedchain.utils import use_pysqlite3

    use_pysqlite3()
    import chromadb

from chromadb.config import Settings

from embedchain.vectordb.base_vector_db import BaseVectorDB


class ChromaDB(BaseVectorDB):
    """Vector database using ChromaDB."""

    def __init__(self, db_dir=None, embedding_fn=None, host=None, port=None):
        self.embedding_fn = embedding_fn

        if not hasattr(embedding_fn, "__call__"):
            raise ValueError("Embedding function is not a function")

        if host and port:
            logging.info(f"Connecting to ChromaDB server: {host}:{port}")
            self.settings = Settings(chroma_server_host=host, chroma_server_http_port=port)
            self.client = chromadb.HttpClient(self.settings)
        else:
            if db_dir is None:
                db_dir = "db"
            self.settings = Settings(anonymized_telemetry=False, allow_reset=True)
            self.client = chromadb.PersistentClient(
                path=db_dir,
                settings=self.settings,
            )
        super().__init__()

    def _get_or_create_db(self):
        """Get or create the database."""
        return self.client

    def _get_or_create_collection(self, name):
        """Get or create the collection."""
        self.collection = self.client.get_or_create_collection(
            name=name,
            embedding_function=self.embedding_fn,
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

    def count(self) -> int:
        return self.collection.count()

    def reset(self):
        # Delete all data from the database
        self.client.reset()
