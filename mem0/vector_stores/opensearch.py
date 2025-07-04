import logging
import time
from typing import Any, Dict, List, Optional

try:
    from opensearchpy import OpenSearch, RequestsHttpConnection
except ImportError:
    raise ImportError("OpenSearch requires extra dependencies. Install with `pip install opensearch-py`") from None

from pydantic import BaseModel

from mem0.configs.vector_stores.opensearch import OpenSearchConfig
from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: str
    score: float
    payload: Dict


class OpenSearchDB(VectorStoreBase):
    def __init__(self, **kwargs):
        config = OpenSearchConfig(**kwargs)

        # Initialize OpenSearch client
        self.client = OpenSearch(
            hosts=[{"host": config.host, "port": config.port or 9200}],
            http_auth=config.http_auth
            if config.http_auth
            else ((config.user, config.password) if (config.user and config.password) else None),
            use_ssl=config.use_ssl,
            verify_certs=config.verify_certs,
            connection_class=RequestsHttpConnection,
            pool_maxsize=20,
        )

        self.collection_name = config.collection_name
        self.embedding_model_dims = config.embedding_model_dims
        self.create_col(self.collection_name, self.embedding_model_dims)

    def create_index(self) -> None:
        """Create OpenSearch index with proper mappings if it doesn't exist."""
        index_settings = {
            "settings": {
                "index": {"number_of_replicas": 1, "number_of_shards": 5, "refresh_interval": "10s", "knn": True}
            },
            "mappings": {
                "properties": {
                    "text": {"type": "text"},
                    "vector_field": {
                        "type": "knn_vector",
                        "dimension": self.embedding_model_dims,
                        "method": {"engine": "nmslib", "name": "hnsw", "space_type": "cosinesimil"},
                    },
                    "metadata": {"type": "object", "properties": {"user_id": {"type": "keyword"}}},
                }
            },
        }

        if not self.client.indices.exists(index=self.collection_name):
            self.client.indices.create(index=self.collection_name, body=index_settings)
            logger.info(f"Created index {self.collection_name}")
        else:
            logger.info(f"Index {self.collection_name} already exists")

    def create_col(self, name: str, vector_size: int) -> None:
        """Create a new collection (index in OpenSearch)."""
        index_settings = {
            "settings": {"index.knn": True},
            "mappings": {
                "properties": {
                    "vector_field": {
                        "type": "knn_vector",
                        "dimension": vector_size,
                        "method": {"engine": "nmslib", "name": "hnsw", "space_type": "cosinesimil"},
                    },
                    "payload": {"type": "object"},
                    "id": {"type": "keyword"},
                }
            },
        }

        if not self.client.indices.exists(index=name):
            logger.warning(f"Creating index {name}, it might take 1-2 minutes...")
            self.client.indices.create(index=name, body=index_settings)

            # Wait for index to be ready
            max_retries = 180  # 3 minutes timeout
            retry_count = 0
            while retry_count < max_retries:
                try:
                    # Check if index is ready by attempting a simple search
                    self.client.search(index=name, body={"query": {"match_all": {}}})
                    time.sleep(1)
                    logger.info(f"Index {name} is ready")
                    return
                except Exception:
                    retry_count += 1
                    if retry_count == max_retries:
                        raise TimeoutError(f"Index {name} creation timed out after {max_retries} seconds")
                    time.sleep(0.5)

    def insert(
        self, vectors: List[List[float]], payloads: Optional[List[Dict]] = None, ids: Optional[List[str]] = None
    ) -> List[OutputData]:
        """Insert vectors into the index."""
        if not ids:
            ids = [str(i) for i in range(len(vectors))]

        if payloads is None:
            payloads = [{} for _ in range(len(vectors))]

        for i, (vec, id_) in enumerate(zip(vectors, ids)):
            body = {
                "vector_field": vec,
                "payload": payloads[i],
                "id": id_,
            }
            self.client.index(index=self.collection_name, body=body)

        results = []

        return results

    def search(
        self, query: str, vectors: List[float], limit: int = 5, filters: Optional[Dict] = None
    ) -> List[OutputData]:
        """Search for similar vectors using OpenSearch k-NN search with optional filters."""

        # Base KNN query
        knn_query = {
            "knn": {
                "vector_field": {
                    "vector": vectors,
                    "k": limit * 2,
                }
            }
        }

        # Start building the full query
        query_body = {"size": limit * 2, "query": None}

        # Prepare filter conditions if applicable
        filter_clauses = []
        if filters:
            for key in ["user_id", "run_id", "agent_id"]:
                value = filters.get(key)
                if value:
                    filter_clauses.append({"term": {f"payload.{key}.keyword": value}})

        # Combine knn with filters if needed
        if filter_clauses:
            query_body["query"] = {"bool": {"must": knn_query, "filter": filter_clauses}}
        else:
            query_body["query"] = knn_query

        # Execute search
        response = self.client.search(index=self.collection_name, body=query_body)

        hits = response["hits"]["hits"]
        results = [
            OutputData(id=hit["_source"].get("id"), score=hit["_score"], payload=hit["_source"].get("payload", {}))
            for hit in hits
        ]
        return results

    def delete(self, vector_id: str) -> None:
        """Delete a vector by custom ID."""
        # First, find the document by custom ID
        search_query = {"query": {"term": {"id": vector_id}}}

        response = self.client.search(index=self.collection_name, body=search_query)
        hits = response.get("hits", {}).get("hits", [])

        if not hits:
            return

        opensearch_id = hits[0]["_id"]

        # Delete using the actual document ID
        self.client.delete(index=self.collection_name, id=opensearch_id)

    def update(self, vector_id: str, vector: Optional[List[float]] = None, payload: Optional[Dict] = None) -> None:
        """Update a vector and its payload using the custom 'id' field."""

        # First, find the document by custom ID
        search_query = {"query": {"term": {"id": vector_id}}}

        response = self.client.search(index=self.collection_name, body=search_query)
        hits = response.get("hits", {}).get("hits", [])

        if not hits:
            return

        opensearch_id = hits[0]["_id"]  # The actual document ID in OpenSearch

        # Prepare updated fields
        doc = {}
        if vector is not None:
            doc["vector_field"] = vector
        if payload is not None:
            doc["payload"] = payload

        if doc:
            try:
                response = self.client.update(index=self.collection_name, id=opensearch_id, body={"doc": doc})
            except Exception:
                pass

    def get(self, vector_id: str) -> Optional[OutputData]:
        """Retrieve a vector by ID."""
        try:
            # First check if index exists
            if not self.client.indices.exists(index=self.collection_name):
                logger.info(f"Index {self.collection_name} does not exist, creating it...")
                self.create_col(self.collection_name, self.embedding_model_dims)
                return None

            search_query = {"query": {"term": {"id": vector_id}}}
            response = self.client.search(index=self.collection_name, body=search_query)

            hits = response["hits"]["hits"]

            if not hits:
                return None

            return OutputData(id=hits[0]["_source"].get("id"), score=1.0, payload=hits[0]["_source"].get("payload", {}))
        except Exception as e:
            logger.error(f"Error retrieving vector {vector_id}: {str(e)}")
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

    def list(self, filters: Optional[Dict] = None, limit: Optional[int] = None) -> List[OutputData]:
        try:
            """List all memories with optional filters."""
            query: Dict = {"query": {"match_all": {}}}

            filter_clauses = []
            if filters:
                for key in ["user_id", "run_id", "agent_id"]:
                    value = filters.get(key)
                    if value:
                        filter_clauses.append({"term": {f"payload.{key}.keyword": value}})

            if filter_clauses:
                query["query"] = {"bool": {"filter": filter_clauses}}

            if limit:
                query["size"] = limit

            response = self.client.search(index=self.collection_name, body=query)
            hits = response["hits"]["hits"]

            return [
                [
                    OutputData(id=hit["_source"].get("id"), score=1.0, payload=hit["_source"].get("payload", {}))
                    for hit in hits
                ]
            ]
        except Exception:
            return []

    def reset(self):
        """Reset the index by deleting and recreating it."""
        logger.warning(f"Resetting index {self.collection_name}...")
        self.delete_col()
        self.create_col(self.collection_name, self.embedding_model_dims)
