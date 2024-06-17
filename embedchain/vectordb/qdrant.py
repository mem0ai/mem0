import copy
import os
from typing import Any, Optional, Union

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models
    from qdrant_client.http.models import Batch
    from qdrant_client.models import Distance, VectorParams
except ImportError:
    raise ImportError("Qdrant requires extra dependencies. Install with `pip install embedchain[qdrant]`") from None

from tqdm import tqdm

from embedchain.config.vectordb.qdrant import QdrantDBConfig
from embedchain.vectordb.base import BaseVectorDB


class QdrantDB(BaseVectorDB):
    """
    Qdrant as vector database
    """

    BATCH_SIZE = 10

    def __init__(self, config: QdrantDBConfig = None):
        """
        Qdrant as vector database
        :param config. Qdrant database config to be used for connection
        """
        if config is None:
            config = QdrantDBConfig()
        else:
            if not isinstance(config, QdrantDBConfig):
                raise TypeError(
                    "config is not a `QdrantDBConfig` instance. "
                    "Please make sure the type is right and that you are passing an instance."
                )
        self.config = config
        self.client = QdrantClient(url=os.getenv("QDRANT_URL"), api_key=os.getenv("QDRANT_API_KEY"))
        # Call parent init here because embedder is needed
        super().__init__(config=self.config)

    def _initialize(self):
        """
        This method is needed because `embedder` attribute needs to be set externally before it can be initialized.
        """
        if not self.embedder:
            raise ValueError("Embedder not set. Please set an embedder with `set_embedder` before initialization.")

        self.collection_name = self._get_or_create_collection()
        all_collections = self.client.get_collections()
        collection_names = [collection.name for collection in all_collections.collections]
        if self.collection_name not in collection_names:
            self.client.recreate_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.embedder.vector_dimension,
                    distance=Distance.COSINE,
                    hnsw_config=self.config.hnsw_config,
                    quantization_config=self.config.quantization_config,
                    on_disk=self.config.on_disk,
                ),
            )

    def _get_or_create_db(self):
        return self.client

    def _get_or_create_collection(self):
        return f"{self.config.collection_name}-{self.embedder.vector_dimension}".lower().replace("_", "-")

    def get(self, ids: Optional[list[str]] = None, where: Optional[dict[str, any]] = None, limit: Optional[int] = None):
        """
        Get existing doc ids present in vector database

        :param ids: _list of doc ids to check for existence
        :type ids: list[str]
        :param where: to filter data
        :type where: dict[str, any]
        :param limit: The number of entries to be fetched
        :type limit: Optional int, defaults to None
        :return: All the existing IDs
        :rtype: Set[str]
        """

        keys = set(where.keys() if where is not None else set())

        qdrant_must_filters = []

        if ids:
            qdrant_must_filters.append(
                models.FieldCondition(
                    key="identifier",
                    match=models.MatchAny(
                        any=ids,
                    ),
                )
            )

        if len(keys) > 0:
            for key in keys:
                qdrant_must_filters.append(
                    models.FieldCondition(
                        key="metadata.{}".format(key),
                        match=models.MatchValue(
                            value=where.get(key),
                        ),
                    )
                )

        offset = 0
        existing_ids = []
        metadatas = []
        while offset is not None:
            response = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=models.Filter(must=qdrant_must_filters),
                offset=offset,
                limit=self.BATCH_SIZE,
            )
            offset = response[1]
            for doc in response[0]:
                existing_ids.append(doc.payload["identifier"])
                metadatas.append(doc.payload["metadata"])
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
        embeddings = self.embedder.embedding_fn(documents)

        payloads = []
        qdrant_ids = []
        for id, document, metadata in zip(ids, documents, metadatas):
            metadata["text"] = document
            qdrant_ids.append(id)
            payloads.append({"identifier": id, "text": document, "metadata": copy.deepcopy(metadata)})

        for i in tqdm(range(0, len(qdrant_ids), self.BATCH_SIZE), desc="Adding data in batches"):
            self.client.upsert(
                collection_name=self.collection_name,
                points=Batch(
                    ids=qdrant_ids[i : i + self.BATCH_SIZE],
                    payloads=payloads[i : i + self.BATCH_SIZE],
                    vectors=embeddings[i : i + self.BATCH_SIZE],
                ),
                **kwargs,
            )

    def query(
        self,
        input_query: str,
        n_results: int,
        where: dict[str, any],
        citations: bool = False,
        **kwargs: Optional[dict[str, Any]],
    ) -> Union[list[tuple[str, dict]], list[str]]:
        """
        query contents from vector database based on vector similarity
        :param input_query: query string
        :type input_query: str
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
        keys = set(where.keys() if where is not None else set())

        qdrant_must_filters = []
        if len(keys) > 0:
            for key in keys:
                qdrant_must_filters.append(
                    models.FieldCondition(
                        key="metadata.{}".format(key),
                        match=models.MatchValue(
                            value=where.get(key),
                        ),
                    )
                )

        results = self.client.search(
            collection_name=self.collection_name,
            query_filter=models.Filter(must=qdrant_must_filters),
            query_vector=query_vector,
            limit=n_results,
            **kwargs,
        )

        contexts = []
        for result in results:
            context = result.payload["text"]
            if citations:
                metadata = result.payload["metadata"]
                metadata["score"] = result.score
                contexts.append(tuple((context, metadata)))
            else:
                contexts.append(context)
        return contexts

    def count(self) -> int:
        response = self.client.get_collection(collection_name=self.collection_name)
        return response.points_count

    def reset(self):
        self.client.delete_collection(collection_name=self.collection_name)
        self._initialize()

    def set_collection_name(self, name: str):
        """
        Set the name of the collection. A collection is an isolated space for vectors.

        :param name: Name of the collection.
        :type name: str
        """
        if not isinstance(name, str):
            raise TypeError("Collection name must be a string")
        self.config.collection_name = name
        self.collection_name = self._get_or_create_collection()

    @staticmethod
    def _generate_query(where: dict):
        must_fields = []
        for key, value in where.items():
            must_fields.append(
                models.FieldCondition(
                    key=f"metadata.{key}",
                    match=models.MatchValue(
                        value=value,
                    ),
                )
            )
        return models.Filter(must=must_fields)

    def delete(self, where: dict):
        db_filter = self._generate_query(where)
        self.client.delete(collection_name=self.collection_name, points_selector=db_filter)