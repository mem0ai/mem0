import os
from typing import Callable, Optional

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

from embedchain.vectordb.base_vector_db import BaseVectorDB


class EsDB(BaseVectorDB):
    """
    Elasticsearch as vector database
        :param embedding_fn: Function to generate embedding vectors.
        :param config: Optional. elastic search client
    """

    def __init__(
        self,
        embedding_fn: Callable[[list[str]], list[str]] = None,
        es_client: Optional[Elasticsearch] = None,
        vector_dim: int = None,
    ):
        if not hasattr(embedding_fn, "__call__"):
            raise ValueError("Embedding function is not a function")
        self.embedding_fn = embedding_fn
        endpoint = os.getenv("ES_ENDPOINT")
        api_key_id = os.getenv("ES_API_KEY_ID")
        api_key = os.getenv("ES_API_KEY")
        api_key_id = api_key_id if api_key_id is not None else ""
        api_key = api_key if api_key is not None else ""
        if not endpoint and not es_client:
            raise ValueError("Elasticsearch endpoint is required to connect")
        if vector_dim is None:
            raise ValueError("Vector Dimension is required to refer correct index and mapping")
        self.client = es_client if es_client is not None else Elasticsearch(endpoint, api_key=(api_key_id, api_key))
        self.vector_dim = vector_dim
        self.es_index = f"embedchain_store_{self.vector_dim}"
        self.bulk = bulk
        index_settings = {
            "mappings": {
                "properties": {
                    "text": {"type": "text"},
                    "text_vector": {"type": "dense_vector", "index": False, "dims": self.vector_dim},
                }
            }
        }
        if not self.client.indices.exists(index=self.es_index):
            # create index if not exist
            print("Creating index", self.es_index, index_settings)
            self.client.indices.create(index=self.es_index, body=index_settings)
        super().__init__()

    def _get_or_create_db(self):
        return self.client

    def _get_or_create_collection(self):
        """Note: nothing to return here. Discuss later"""
