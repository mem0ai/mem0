import logging
from typing import Any, Dict, List, Optional

try:
    from opensearchpy import OpenSearch, RequestsHttpConnection
    from opensearchpy.helpers import bulk
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


def _is_aoss_enabled(http_auth: Any) -> bool:
    """Check if the service is Amazon OpenSearch Serverless (AOSS)."""
    if http_auth is not None and hasattr(http_auth, "service") and http_auth.service == "aoss":
        return True
    return False


def _validate_aoss_with_engines(is_aoss: bool, engine: str) -> None:
    """Validate AOSS with the engine."""
    if is_aoss and engine != "nmslib" and engine != "faiss":
        raise ValueError("Amazon OpenSearch Service Serverless only supports `nmslib` or `faiss` engines")


def _get_space_type_for_engine(engine: str) -> str:
    """Get the appropriate space_type for the engine."""
    if engine == "faiss":
        # FAISS with HNSW supports l2 (Euclidean) and innerproduct, but not cosinesimil
        return "l2"
    else:
        # NMSLIB and Lucene support cosinesimil
        return "cosinesimil"


class OpenSearchDB(VectorStoreBase):
    def __init__(self, **kwargs):
        config = OpenSearchConfig(**kwargs)

        # Check if using Amazon OpenSearch Serverless
        self.is_aoss = _is_aoss_enabled(http_auth=config.http_auth)
        
        # Initialize OpenSearch client
        # Handle both URL string for AOSS and host/port dictionary for standard OpenSearch
        if isinstance(config.host, str) and (config.host.startswith("https://") or config.host.startswith("http://")):
            # Using URL format for host (common with AOSS)
            self.client = OpenSearch(
                hosts=config.host,
                http_auth=config.http_auth
                if config.http_auth
                else ((config.user, config.password) if (config.user and config.password) else None),
                use_ssl=config.use_ssl,
                verify_certs=config.verify_certs,
                connection_class=RequestsHttpConnection,
            )
        else:
            # Traditional host/port configuration
            self.client = OpenSearch(
                hosts=[{"host": config.host, "port": config.port or 9200}],
                http_auth=config.http_auth
                if config.http_auth
                else ((config.user, config.password) if (config.user and config.password) else None),
                use_ssl=config.use_ssl,
                verify_certs=config.verify_certs,
                connection_class=RequestsHttpConnection,
            )

        self.collection_name = config.collection_name
        self.embedding_model_dims = config.embedding_model_dims
        self.engine = config.engine if hasattr(config, "engine") else "nmslib"
        
        # Validate AOSS compatibility if enabled
        if self.is_aoss:
            _validate_aoss_with_engines(self.is_aoss, self.engine)
            
        # Determine appropriate space_type for the engine
        self.space_type = _get_space_type_for_engine(self.engine)

        # Create index only if auto_create_index is True
        if config.auto_create_index:
            self.create_index()

    def create_index(self) -> None:
        """Create OpenSearch index with proper mappings if it doesn't exist."""
        # Set refresh_interval based on whether we're using AOSS (needs at least 10s)
        refresh_interval = "10s" if self.is_aoss else "1s"
        
        index_settings = {
            "settings": {
                "index": {"number_of_replicas": 1, "number_of_shards": 5, "refresh_interval": refresh_interval, "knn": True}
            },
            "mappings": {
                "properties": {
                    "text": {"type": "text"},
                    "vector": {
                        "type": "knn_vector",
                        "dimension": self.embedding_model_dims,
                        "method": {"engine": self.engine if self.is_aoss else "lucene", "name": "hnsw", "space_type": self.space_type},
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
            "mappings": {
                "properties": {
                    "vector": {
                        "type": "knn_vector",
                        "dimension": vector_size,
                        "method": {"engine": self.engine if self.is_aoss else "lucene", "name": "hnsw", "space_type": self.space_type},
                    },
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
                "_source": {
                    "vector": vec,
                    "metadata": payloads[i],  # Store metadata in the metadata field
                },
            }
            
            # For AOSS, use "id" instead of "_id"
            if self.is_aoss:
                action["id"] = id_
            else:
                action["_id"] = id_
                
            actions.append(action)

        bulk(self.client, actions)

        results = []
        for i, id_ in enumerate(ids):
            results.append(OutputData(id=id_, score=1.0, payload=payloads[i]))
        return results

    def search(
        self, query: str, vectors: List[float], limit: int = 5, filters: Optional[Dict] = None
    ) -> List[OutputData]:
        """Search for similar vectors using OpenSearch k-NN search with pre-filtering."""
        search_query = {
            "size": limit,
            "query": {
                "knn": {
                    "vector": {
                        "vector": vectors,
                        "k": limit,
                    }
                }
            },
        }

        if filters:
            filter_conditions = [{"term": {f"metadata.{key}": value}} for key, value in filters.items()]

            # AOSS uses filter directly instead of subquery_clause
            if self.is_aoss and self.engine in ["faiss", "nmslib"]:
                search_query["query"]["knn"]["vector"]["filter"] = {"bool": {"filter": filter_conditions}}
            else:
                # Use boolean filter for other engines
                search_query["query"] = {
                    "bool": {
                        "filter": filter_conditions,
                        "must": [
                            {"knn": {"vector": {"vector": vectors, "k": limit}}}
                        ]
                    }
                }

        response = self.client.search(index=self.collection_name, body=search_query)

        results = [
            OutputData(id=hit["_id"], score=hit["_score"], payload=hit["_source"].get("metadata", {}))
            for hit in response["hits"]["hits"]
        ]
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
            return OutputData(id=response["_id"], score=1.0, payload=response["_source"].get("metadata", {}))
        except Exception as e:
            logger.error(f"Error retrieving vector {vector_id}: {e}")
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
        query = {"query": {"match_all": {}}}

        if filters:
            query["query"] = {
                "bool": {"must": [{"term": {f"metadata.{key}": value}} for key, value in filters.items()]}
            }

        if limit:
            query["size"] = limit

        response = self.client.search(index=self.collection_name, body=query)
        return [
            [
                OutputData(id=hit["_id"], score=1.0, payload=hit["_source"].get("metadata", {}))
                for hit in response["hits"]["hits"]
            ]
        ]
        
    def reset(self):
        """Reset the index by deleting and recreating it."""
        logger.warning(f"Resetting index {self.collection_name}...")
        self.delete_col()
        self.create_index()
