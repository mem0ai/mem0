from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
import logging
from typing import List, Optional, Dict, Any

from mem0.vector_stores.base import VectorStoreBase
from mem0.configs.vector_stores.elasticsearch import ElasticsearchConfig

logger = logging.getLogger(__name__)

class OutputData:
    def __init__(self, id: str, score: float, payload: dict):
        self.id = id
        self.score = score
        self.payload = payload

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
        
        # Create index
        self.create_index()
        
    def create_index(self):
        """Create Elasticsearch index with proper mappings if it doesn't exist"""
        index_settings = {
            "mappings": {
                "properties": {
                    "text": {"type": "text"},
                    "embedding": {
                        "type": "dense_vector",
                        "dims": self.vector_dim,
                        "index": True,
                        "similarity": "cosine"
                    },
                    "metadata": {"type": "object"},
                    "user_id": {"type": "keyword"},
                    "hash": {"type": "keyword"}
                }
            }
        }
        
        if not self.client.indices.exists(index=self.collection_name):
            self.client.indices.create(
                index=self.collection_name,
                body=index_settings
            )
            
    def create_col(self, name: str, vector_size: int, distance: str = "cosine"):
        """Create a new collection (index in Elasticsearch)."""
        index_settings = {
            "mappings": {
                "properties": {
                    "vector": {
                        "type": "dense_vector",
                        "dims": vector_size,
                        "index": True,
                        "similarity": "cosine"
                    },
                    "payload": {"type": "object"},
                    "id": {"type": "keyword"}
                }
            }
        }
        
        if not self.client.indices.exists(index=name):
            self.client.indices.create(index=name, body=index_settings)
            logger.info(f"Created index {name}")
            
    def insert(self, vectors: List[List[float]], payloads: Optional[List[Dict]] = None, 
              ids: Optional[List[str]] = None):
        """Insert vectors into the index."""
        if not ids:
            ids = [str(i) for i in range(len(vectors))]
            
        actions = []
        for i, (vec, id_) in enumerate(zip(vectors, ids)):
            action = {
                "_index": self.collection_name,
                "_id": id_,
                "vector": vec,
                "payload": payloads[i] if payloads else {}
            }
            actions.append(action)
            
        bulk(self.client, actions) 

    def search(self, query: List[float], limit: int = 5, filters: Optional[Dict] = None):
        """Search for similar vectors."""
        search_query = {
            "query": {
                "script_score": {
                    "query": {"match_all": {}},
                    "script": {
                        "source": "cosineSimilarity(params.query_vector, 'vector') + 1.0",
                        "params": {"query_vector": query}
                    }
                }
            },
            "size": limit
        }
        
        if filters:
            search_query["query"]["script_score"]["query"] = {
                "bool": {
                    "must": [{"match": {f"payload.{k}": v}} for k, v in filters.items()]
                }
            }
            
        response = self.client.search(index=self.collection_name, body=search_query)
        
        results = []
        for hit in response["hits"]["hits"]:
            results.append({
                "id": hit["_id"],
                "score": hit["_score"],
                "payload": hit["_source"].get("payload", {})
            })
            
        return results
        
    def delete(self, vector_id: str):
        """Delete a vector by ID."""
        self.client.delete(index=self.collection_name, id=vector_id)
        
    def update(self, vector_id: str, vector: Optional[List[float]] = None, 
              payload: Optional[Dict] = None):
        """Update a vector and its payload."""
        doc = {}
        if vector is not None:
            doc["vector"] = vector
        if payload is not None:
            doc["payload"] = payload
            
        self.client.update(
            index=self.collection_name,
            id=vector_id,
            body={"doc": doc}
        )
        
    def get(self, vector_id: str):
        """Retrieve a vector by ID."""
        try:
            response = self.client.get(index=self.collection_name, id=vector_id)
            return {
                "id": response["_id"],
                "vector": response["_source"]["vector"],
                "payload": response["_source"].get("payload", {})
            }
        except:
            return None
            
    def list_cols(self):
        """List all collections (indices)."""
        return list(self.client.indices.get_alias().keys())
        
    def delete_col(self):
        """Delete a collection (index)."""
        self.client.indices.delete(index=self.collection_name)
        
    def col_info(self, name: str):
        """Get information about a collection (index)."""
        return self.client.indices.get(index=name)
        
    def list(self, filters: Optional[Dict] = None, limit: Optional[int] = None):
        """List all memories."""
        query = {"query": {"match_all": {}}}
        
        if filters:
            query["query"] = {
                "bool": {
                    "must": [{"match": {f"payload.{k}": v}} for k, v in filters.items()]
                }
            }
            
        if limit:
            query["size"] = limit
            
        response = self.client.search(index=self.collection_name, body=query)
        
        results = []
        for hit in response["hits"]["hits"]:
            results.append({
                "id": hit["_id"],
                "vector": hit["_source"]["vector"],
                "payload": hit["_source"].get("payload", {})
            })
            
        return results