from enum import Enum
import logging
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel

try:
    import elasticsearch
except ImportError:
    raise ImportError(
        "The 'Elasticsearch' library is required. Please install it using 'pip install elasticsearch'."
    )

from mem0.vector_stores.base import VectorStoreBase


logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: Optional[str]  # memory id
    score: Optional[float]  # distance
    payload: Optional[Dict]  # metadata


class DistanceStrategy(str, Enum):
    """Enumerator of the Distance strategies for calculating distances
    between vectors."""

    EUCLIDEAN_DISTANCE = "EUCLIDEAN_DISTANCE"
    MAX_INNER_PRODUCT = "MAX_INNER_PRODUCT"
    DOT_PRODUCT = "DOT_PRODUCT"
    JACCARD = "JACCARD"
    COSINE = "COSINE"


class ElasticSearchStore(VectorStoreBase):
    def __init__(
        self,
        index_name: str,
        client: Optional[elasticsearch.Elasticsearch] = None,
        endpoint: Optional[str] = None,
        api_key: Optional[int] = None,
        vector_query_field: Optional[str] = "vector",
        query_field: Optional[str] = "text",
        distance_strategy: Optional[
            Literal[
                DistanceStrategy.COSINE,
                DistanceStrategy.DOT_PRODUCT,
                DistanceStrategy.EUCLIDEAN_DISTANCE,
                DistanceStrategy.MAX_INNER_PRODUCT,
            ]
        ] = None,
        strategy: BaseRetrievalStrategy = ApproxRetrievalStrategy(),
    ):
        if client:
            self.client = client
        else:
            self.client = elasticsearch.Elasticsearch(
                endpoint,
                api_key=api_key,
            )
        self.index_name = index_name
        self.query_field = query_field
        self.vector_query_field = vector_query_field
        self.distance_strategy = (
            DistanceStrategy.COSINE
            if distance_strategy is None
            else DistanceStrategy[distance_strategy]
        )
        self.index = self.create_col(index_name)


    def create_col(self, name, vector_size, distance):
        if self.client.indices.exists(index=name, allow_no_indices=True):
            logging.debug(f"Index {name} already exists. Skipping creation.")
            return
        self.client.indices.create(
            index=name,
            mappings={
                "properties": {
                    "vector": {
                        "type": "dense_vector",
                        "dimensions": vector_size,
                        "similarity": distance,
                    }
                }
            },
        )


    def insert(self, vectors: list, payloads: list = None, ids: list = None):
        logger.info(f"Inserting {len(vectors)} vectors into index {self.index_name}")
        self.client.index(index=self.index_name, document=vectors)
        

    def search(self, query, limit=5, filters=None):
        raise NotImplementedError

    def delete(self, vector_id):
        raise NotImplementedError

    def update(self, vector_id, vector=None, payload=None):
        raise NotImplementedError

    def get(self, vector_id):
        raise NotImplementedError

    def list_cols(self):
        raise NotImplementedError

    def delete_col(self, name):
        raise NotImplementedError

    def col_info(self, name):
        raise NotImplementedError
