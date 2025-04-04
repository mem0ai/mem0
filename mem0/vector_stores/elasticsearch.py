import logging
from typing import Any, Dict, List, Optional

try:
    from elasticsearch import Elasticsearch
    from elasticsearch.helpers import bulk
except ImportError:
    raise ImportError("Elasticsearch requires extra dependencies. Install with `pip install elasticsearch`") from None

from pydantic import BaseModel

from mem0.configs.vector_stores.elasticsearch import ElasticsearchConfig
from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: str
    score: float
    payload: Dict


class ElasticsearchDB(VectorStoreBase):
    def __init__(self, **kwargs):
        config = ElasticsearchConfig(**kwargs)

        # Initialize Elasticsearch client
        if config.cloud_id:
            self.client = Elasticsearch(
                cloud_id=config.cloud_id,
                api_key=config.api_key,
                verify_certs=config.verify_certs,
            )
        else:
            self.client = Elasticsearch(
                hosts=[f"{config.host}" if config.port is None else f"{config.host}:{config.port}"],
                basic_auth=(config.user, config.password) if (config.user and config.password) else None,
                verify_certs=config.verify_certs,
            )

        self.collection_name = config.collection_name
        self.vector_dim = config.embedding_model_dims

        # Create index only if auto_create_index is True
        if config.auto_create_index:
            self.create_index()

        if config.custom_search_query:
            self.custom_search_query = config.custom_search_query
        else:
            self.custom_search_query = None

    def create_index(self) -> None:
        """Create Elasticsearch index with proper mappings if it doesn't exist"""
        index_settings = {
            "settings": {"index": {"number_of_replicas": 1, "number_of_shards": 5, "refresh_interval": "1s"}},
            "mappings": {
                "properties": {
                    "text": {"type": "text"},
                    "vector": {"type": "dense_vector", "dims": self.vector_dim, "index": True, "similarity": "cosine"},
                    "metadata": {"type": "object", "properties": {"user_id": {"type": "keyword"}}},
                }
            },
        }

        if not self.client.indices.exists(index=self.collection_name):
            self.client.indices.create(index=self.collection_name, body=index_settings)
            logger.info(f"Created index {self.collection_name}")
        else:
            logger.info(f"Index {self.collection_name} already exists")

    def create_col(self, name: str, vector_size: int, distance: str = "cosine") -> None:
        """Create a new collection (index in Elasticsearch)."""
        index_settings = {
            "mappings": {
                "properties": {
                    "vector": {"type": "dense_vector", "dims": vector_size, "index": True, "similarity": "cosine"},
                    "payload": {"type": "object"},
                    "id": {"type": "keyword"},
                }
            }
        }

        if not self.client.indices.exists(index=name):
            self.client.indices.create(index=name, body=index_settings)
            logger.info(f"Created index {name}")

    def insert(
        self, vectors: List[List[float]], payloads: Optional[List[Dict]] = None, ids: Optional[List[str]] = None
    ) -> List[OutputData]:
        """Insert vectors into the index."""
        if not ids:
            ids = [str(i) for i in range(len(vectors))]

        if payloads is None:
            payloads = [{} for _ in range(len(vectors))]

        actions = []
        for i, (vec, id_) in enumerate(zip(vectors, ids)):
            action = {
                "_index": self.collection_name,
                "_id": id_,
                "_source": {
                    "vector": vec,
                    "metadata": payloads[i],  # Store all metadata in the metadata field
                },
            }
            actions.append(action)

        bulk(self.client, actions)

        results = []
        for i, id_ in enumerate(ids):
            results.append(
                OutputData(
                    id=id_,
                    score=1.0,  # Default score for inserts
                    payload=payloads[i],
                )
            )
        return results

    def search(
        self, query: str, vectors: List[float], limit: int = 5, filters: Optional[Dict] = None
    ) -> List[OutputData]:
        """
        Search with two options:
        1. Use custom search query if provided
        2. Use KNN search on vectors with pre-filtering if no custom search query is provided
        """
        if self.custom_search_query:
            search_query = self.custom_search_query(vectors, limit, filters)
        else:
            search_query = {
                "knn": {"field": "vector", "query_vector": vectors, "k": limit, "num_candidates": limit * 2}
            }
            if filters:
                filter_conditions = []
                for key, value in filters.items():
                    filter_conditions.append({"term": {f"metadata.{key}": value}})
                search_query["knn"]["filter"] = {"bool": {"must": filter_conditions}}

        response = self.client.search(index=self.collection_name, body=search_query)

        results = []
        for hit in response["hits"]["hits"]:
            results.append(
                OutputData(id=hit["_id"], score=hit["_score"], payload=hit.get("_source", {}).get("metadata", {}))
            )

        return results

    def delete(self, vector_id: str) -> None:
        """Delete a vector by ID."""
        self.client.delete(index=self.collection_name, id=vector_id)

    def update(self, vector_id: str, vector: Optional[List[float]] = None, payload: Optional[Dict] = None) -> None:
        """Update a vector and its payload."""
        doc = {}
        if vector is not None:
            doc["vector"] = vector
        if payload is not None:
            doc["metadata"] = payload

        self.client.update(index=self.collection_name, id=vector_id, body={"doc": doc})

    def get(self, vector_id: str) -> Optional[OutputData]:
        """Retrieve a vector by ID."""
        try:
            response = self.client.get(index=self.collection_name, id=vector_id)
            return OutputData(
                id=response["_id"],
                score=1.0,  # Default score for direct get
                payload=response["_source"].get("metadata", {}),
            )
        except KeyError as e:
            logger.warning(f"Missing key in Elasticsearch response: {e}")
            return None
        except TypeError as e:
            logger.warning(f"Invalid response type from Elasticsearch: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error while parsing Elasticsearch response: {e}")
            return None

    def list_cols(self) -> List[str]:
        """List all collections (indices)."""
        return list(self.client.indices.get_alias().keys())

    def delete_col(self) -> None:
        """Delete a collection (index)."""
        self.client.indices.delete(index=self.collection_name)

    def col_info(self, name: str) -> Any:
        """Get information about a collection (index)."""
        return self.client.indices.get(index=name)

    def list(self, filters: Optional[Dict] = None, limit: Optional[int] = None) -> List[List[OutputData]]:
        """List all memories."""
        query: Dict[str, Any] = {"query": {"match_all": {}}}

        if filters:
            filter_conditions = []
            for key, value in filters.items():
                filter_conditions.append({"term": {f"metadata.{key}": value}})
            query["query"] = {"bool": {"must": filter_conditions}}

        if limit:
            query["size"] = limit

        response = self.client.search(index=self.collection_name, body=query)

        results = []
        for hit in response["hits"]["hits"]:
            results.append(
                OutputData(
                    id=hit["_id"],
                    score=1.0,  # Default score for list operation
                    payload=hit.get("_source", {}).get("metadata", {}),
                )
            )

        return [results]
