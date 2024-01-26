import logging
import os
from typing import Optional, Union

try:
    import pinecone
except ImportError:
    raise ImportError(
        "Pinecone requires extra dependencies. Install with `pip install --upgrade 'embedchain[pinecone]'`"
    ) from None

from embedchain.config.vectordb.pinecone import PineconeDBConfig
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.utils.misc import chunks
from embedchain.vectordb.base import BaseVectorDB


@register_deserializable
class PineconeDB(BaseVectorDB):
    """
    Pinecone as vector database
    """

    BATCH_SIZE = 100

    def __init__(
        self,
        config: Optional[PineconeDBConfig] = None,
    ):
        """Pinecone as vector database.

        :param config: Pinecone database config, defaults to None
        :type config: PineconeDBConfig, optional
        :raises ValueError: No config provided
        """
        if config is None:
            self.config = PineconeDBConfig()
        else:
            if not isinstance(config, PineconeDBConfig):
                raise TypeError(
                    "config is not a `PineconeDBConfig` instance. "
                    "Please make sure the type is right and that you are passing an instance."
                )
            self.config = config
        self._setup_pinecone_index()
        # Call parent init here because embedder is needed
        super().__init__(config=self.config)

    def _initialize(self):
        """
        This method is needed because `embedder` attribute needs to be set externally before it can be initialized.
        """
        if not self.embedder:
            raise ValueError("Embedder not set. Please set an embedder with `set_embedder` before initialization.")

    def _setup_pinecone_index(self):
        """
        Loads the Pinecone index or creates it if not present.
        """
        api_key = self.config.api_key or os.environ.get("PINECONE_API_KEY")
        if not api_key:
            raise ValueError("Please set the PINECONE_API_KEY environment variable or pass it in config.")
        self.client = pinecone.Pinecone(api_key=api_key, **self.config.extra_params)
        indexes = self.client.list_indexes().names()
        if indexes is None or self.config.index_name not in indexes:
            if self.config.pod_config:
                spec = pinecone.PodSpec(**self.config.pod_config)
            elif self.config.serverless_config:
                spec = pinecone.ServerlessSpec(**self.config.serverless_config)
            else:
                raise ValueError("No pod_config or serverless_config found.")

            self.client.create_index(
                name=self.config.index_name,
                metric=self.config.metric,
                dimension=self.config.vector_dimension,
                spec=spec,
            )
        self.pinecone_index = self.client.Index(self.config.index_name)

    def get(self, ids: Optional[list[str]] = None, where: Optional[dict[str, any]] = None, limit: Optional[int] = None):
        """
        Get existing doc ids present in vector database

        :param ids: _list of doc ids to check for existence
        :type ids: list[str]
        :param where: to filter data
        :type where: dict[str, any]
        :return: ids
        :rtype: Set[str]
        """
        existing_ids = list()
        metadatas = []

        if ids is not None:
            for i in range(0, len(ids), 1000):
                result = self.pinecone_index.fetch(ids=ids[i : i + 1000])
                vectors = result.get("vectors")
                batch_existing_ids = list(vectors.keys())
                existing_ids.extend(batch_existing_ids)
                metadatas.extend([vectors.get(ids).get("metadata") for ids in batch_existing_ids])

        if where is not None:
            logging.warning("Filtering is not supported by Pinecone")

        return {"ids": existing_ids, "metadatas": metadatas}

    def add(
        self,
        documents: list[str],
        metadatas: list[object],
        ids: list[str],
        **kwargs: Optional[dict[str, any]],
    ):
        """add data in vector database

        :param documents: list of texts to add
        :type documents: list[str]
        :param metadatas: list of metadata associated with docs
        :type metadatas: list[object]
        :param ids: ids of docs
        :type ids: list[str]
        """
        docs = []
        print("Adding documents to Pinecone...")
        embeddings = self.embedder.embedding_fn(documents)
        for id, text, metadata, embedding in zip(ids, documents, metadatas, embeddings):
            docs.append(
                {
                    "id": id,
                    "values": embedding,
                    "metadata": {**metadata, "text": text},
                }
            )

        for chunk in chunks(docs, self.BATCH_SIZE, desc="Adding chunks in batches"):
            self.pinecone_index.upsert(chunk, **kwargs)

    def query(
        self,
        input_query: list[str],
        n_results: int,
        where: dict[str, any],
        citations: bool = False,
        **kwargs: Optional[dict[str, any]],
    ) -> Union[list[tuple[str, dict]], list[str]]:
        """
        query contents from vector database based on vector similarity
        :param input_query: list of query string
        :type input_query: list[str]
        :param n_results: no of similar documents to fetch from database
        :type n_results: int
        :param where: Optional. to filter data
        :type where: dict[str, any]
        :param citations: we use citations boolean param to return context along with the answer.
        :type citations: bool, default is False.
        :return: The content of the document that matched your query,
        along with url of the source and doc_id (if citations flag is true)
        :rtype: list[str], if citations=False, otherwise list[tuple[str, str, str]]
        """
        query_vector = self.embedder.embedding_fn([input_query])[0]
        query_filter = self._generate_filter(where)
        data = self.pinecone_index.query(
            vector=query_vector,
            filter=query_filter,
            top_k=n_results,
            include_metadata=True,
            **kwargs,
        )
        contexts = []
        for doc in data.get("matches", []):
            metadata = doc.get("metadata", {})
            context = metadata.get("text")
            if citations:
                metadata["score"] = doc.get("score")
                contexts.append(tuple((context, metadata)))
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

    def count(self) -> int:
        """
        Count number of documents/chunks embedded in the database.

        :return: number of documents
        :rtype: int
        """
        data = self.pinecone_index.describe_index_stats()
        return data["total_vector_count"]

    def _get_or_create_db(self):
        """Called during initialization"""
        return self.client

    def reset(self):
        """
        Resets the database. Deletes all embeddings irreversibly.
        """
        # Delete all data from the database
        self.client.delete_index(self.config.index_name)
        self._setup_pinecone_index()

    @staticmethod
    def _generate_filter(where: dict):
        query = {}
        for k, v in where.items():
            query[k] = {"$eq": v}
        return query

    def delete(self, where: dict):
        """Delete from database.
        :param ids: list of ids to delete
        :type ids: list[str]
        """
        # Deleting with filters is not supported for `starter` index type.
        # Follow `https://docs.pinecone.io/docs/metadata-filtering#deleting-vectors-by-metadata-filter` for more details
        db_filter = self._generate_filter(where)
        try:
            self.pinecone_index.delete(filter=db_filter)
        except Exception as e:
            print(f"Failed to delete from Pinecone: {e}")
            return
