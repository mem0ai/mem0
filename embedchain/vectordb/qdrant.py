import copy
import os
from typing import Dict, List, Optional
import uuid

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams
    from qdrant_client.http import models
    from qdrant_client.http.models import Batch
except ImportError:
    raise ImportError("Qdrant requires extra dependencies. Install with `pip install embedchain[qdrant]`") from None

from embedchain.config.vectordb.qdrant import QdrantDBConfig
from embedchain.vectordb.base import BaseVectorDB


class QdrantDB(BaseVectorDB):
    BATCH_SIZE = 10

    def __init__(
            self,
            config: QdrantDBConfig = None
    ):
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
        self.metadata_keys = {"data_type", "doc_id", "url", "hash", "app_id", "text"}
        all_collections = self.client.get_collections()
        collection_names = [collection.name for collection in all_collections.collections]
        if not self.collection_name in collection_names:
            self.client.recreate_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.embedder.vector_dimension, distance=Distance.COSINE,
                                            hnsw_config=self.config.hnsw_config,
                                            quantization_config=self.config.quantization_config,
                                            on_disk=self.config.on_disk),
            )

    def _get_or_create_db(self):
        return self.client

    def _get_or_create_collection(self):
        return f"{self.config.collection_name}-{self.embedder.vector_dimension}".lower().replace("_", "-")

    def get(self, ids: Optional[List[str]] = None, where: Optional[Dict[str, any]] = None, limit: Optional[int] = None):
        """
        Get existing doc ids present in vector database
        :param ids: list of doc ids to check for existence
        :param where: Optional. to filter data
        """
        if ids is None or len(ids) == 0:
            return {"ids": []}

        keys = set(where.keys() if where is not None else set())

        qdrant_must_filters = [
            models.FieldCondition(
                key="identifier",
                match=models.MatchAny(
                    any=ids,
                ),
            )
        ]
        if len(keys.intersection(self.metadata_keys)) != 0:
            for key in keys.intersection(self.metadata_keys):
                qdrant_must_filters.append(
                    models.FieldCondition(
                        key="payload.metadata.{}".format(key),
                        match=models.MatchValue(
                            value=where.get(key),
                        ),
                    )
                )

        offset = 0
        existing_ids = []
        while True:
            response = self.client.scroll(collection_name=self.collection_name, scroll_filter=models
                                          .Filter(must=qdrant_must_filters), offset=offset, limit=self.BATCH_SIZE)
            if len(response[0]) == 0:
                break
            for doc in response[0]["result"]:
                existing_ids.append(doc["id"])
        return {"ids": existing_ids}

    def add(
            self,
            embeddings: List[List[float]],
            documents: List[str],
            metadatas: List[object],
            ids: List[str],
            skip_embedding: bool
    ):
        """
        add data in vector database
        :param documents: list of texts to add
        :param metadatas: list of metadata associated with docs
        :param ids: ids of docs
        """
        if not skip_embedding:
            embeddings = self.embedder.embedding_fn(documents)

        payloads = []
        qdrant_ids = []
        for id, document, metadata in zip(ids, documents, metadatas):
            metadata["text"] = document
            qdrant_ids.append(str(uuid.uuid4()))
            payloads.append({
                "identifier": id,
                "text": document,
                "metadata": copy.deepcopy(metadata)
            })
        for i in range(0, len(qdrant_ids), self.BATCH_SIZE):
            self.client.upsert(
                collection_name=self.collection_name,
                points=Batch(
                    ids=qdrant_ids[i: i + self.BATCH_SIZE],
                    payloads=payloads[i: i + self.BATCH_SIZE],
                    vectors=embeddings[i: i + self.BATCH_SIZE],
                ),
            )

    def query(self, input_query: List[str], n_results: int, where: Dict[str, any], skip_embedding: bool) -> List[str]:
        """
        query contents from vector database based on vector similarity
        :param input_query: list of query string
        :param n_results: no of similar documents to fetch from database
        :param where: Optional. to filter data
        """
        if not skip_embedding:
            query_vector = self.embedder.embedding_fn([input_query])[0]
        else:
            query_vector = input_query

        keys = set(where.keys() if where is not None else set())

        qdrant_must_filters = []
        if len(keys.intersection(self.metadata_keys)) != 0:
            for key in keys.intersection(self.metadata_keys):
                qdrant_must_filters.append(
                    models.FieldCondition(
                        key="payload.metadata.{}".format(key),
                        match=models.MatchValue(
                            value=where.get(key),
                        ),
                    )
                )
        results = self.client.search(collection_name=self.collection_name,
                                     query_filter=models.Filter(must=qdrant_must_filters), query_vector=query_vector,
                                     limit=n_results)
        response = []
        for result in results:
            response.append(result.payload.get("text", ""))
        return response

    def count(self) -> int:
        response = self.client.get_collection(collection_name=self.collection_name)
        return response.points_count

    def reset(self):
        self.client.delete_collection(collection_name=self.collection_name)
        self._initialize()
