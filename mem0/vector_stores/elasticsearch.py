import logging
import json
from typing import Dict, Optional, List, Any

from pydantic import BaseModel


from mem0.vector_stores.base import VectorStoreBase

try:
    from elasticsearch import Elasticsearch, helpers
except ImportError:
    raise ImportError("The 'elasticsearch' library is required. Please install it using 'pip install elasticsearch'.")

logger = logging.getLogger(__name__)

class OutputData(BaseModel):
    id: Optional[str]  # memory id
    score: Optional[float]  # distance
    metadata: Optional[Dict]  

class ElasticsearchDB(VectorStoreBase):
    def __init__(
        self,
        collection_name: str,
        embedding_model_dims: int,
        metric_type: str,
        url: str,
        api_key: str,
    ) -> None:
        """Initialize the Elasticsearch.

        Args:
            collection_name (str): Name of the collection (defaults to mem0).
            embedding_model_dims (int): Dimensions of the embedding model (defaults to 2048).
            metric_type (str): Metric type for similarity search (defaults to dot_product).
            url (str): url for Elasticsearch server.
            api_key (str): api_key for Elasticsearch server.
        """
        self.collection_name = collection_name
        self.embedding_model_dims = embedding_model_dims
        self.metric_type = metric_type
        self.client = Elasticsearch(url, api_key=api_key)
        self.create_col(
            collection_name=self.collection_name,
            vector_size=self.embedding_model_dims,
            metric_type=self.metric_type,
        )
        
    def create_col(
        self,
        collection_name: str,
        vector_size: str,
        metric_type: str,
    ) -> None:
        """Create a new collection with index_type AUTOINDEX.

        Args:
            collection_name (str): Name of the collection (defaults to mem0).
            vector_size (str): Dimensions of the embedding model (defaults to 2048).
            metric_type (str): etric type for similarity search. Defaults to dot_product.
        """
        if self.client.indices.exists(index=collection_name):
            logger.info(f"Collection {collection_name} already exists. Skipping creation.")
        else:
            fields = {
                'id': {
                    'type': 'keyword'
                },
                'vectors': {
                    'type': 'dense_vector', 
                    'dims': vector_size, 
                    'index': True, 
                    'similarity': metric_type
                },
                'metadata': {
                    'type': 'object', 
                    'dynamic': True
                }
            }
            self.client.indices.create(index=collection_name, body={
                'mappings': {
                    'properties': fields
                }
            })
            
    def insert(self, ids, vectors, metadatas):
        """Insert vectors into a collection.

        Args:
            vectors (List[List[float]]): List of vectors to insert.
            metadatas (List[Dict], optional): List of metadatas corresponding to vectors.
            ids (List[str], optional): List of IDs corresponding to vectors.
        """
        documents = []
        for idx, vector, metadata in zip(ids, vectors, metadatas):
            fields = {
                "id": idx, 
                "vectors": vector,
                "metadata": metadata
            }
            documents.append({
                '_index': self.collection_name,
                '_source': fields
            })
        helpers.bulk(self.client, documents)
        
    def _create_filter(self, filters: dict):
        """Prepare filters for efficient query.

        Args:
            filters (dict): filters [user_id, agent_id, run_id]

        Returns:
            dict: formated filter.
        """
        process_filter = {}
        FILTER_PREFIX = "metadata"
        for k, v in filters.items():
            process_filter[f"{FILTER_PREFIX}.{k}"] = v
        return process_filter

    def _parse_output(self, data: list):
        """
        Parse the output data.

        Args:
            data (list): Output data.

        Returns:
            List[OutputData]: Parsed output data.
        """
        memory = []
        for value in data:
            source = value.get('_source')
            
            uid, score, metadata = (
                source.get('id'),
                value.get('_score'),
                source.get('metadata'),
            )
            
            memory_obj = OutputData(id=uid, score=score, metadata=metadata)
            memory.append(memory_obj)
                
        return memory
    
    def _get_id_from_resp(self, resp: dict):
        count = resp['hits']['total']['value']
        _id = None
        if count > 0:
            _id =  resp['hits']['hits'][0]['_id'] 
        return _id

    def search(self, query: list, limit: int = 5, filters: dict = None) -> list:
        """
        Search for similar vectors.

        Args:
            query (List[float]): Query vector.
            limit (int, optional): Number of results to return. Defaults to 5.
            filters (Dict, optional): Filters to apply to the search. Defaults to None.

        Returns:
            list: Search results.
        """
        process_filter = self._create_filter(filters)
        process_query = {
            'query': {
                'bool': {
                    'must': {
                        'knn': {
                            'field': 'vectors',
                            'query_vector': query,
                            'k': limit,
                        }
                    },
                    'filter': {
                        'term': process_filter
                    }
                }
            }
        }
        response = self.client.search(index=self.collection_name, body=process_query)
        result = self._parse_output(response['hits']['hits'])
        return result
        
    def delete(self, vector_id):
        """
        Delete a vector by ID.

        Args:
            vector_id (str): ID of the vector to delete.
        """
        query = {
            'query': {
                'term': {
                    'id': vector_id
                }
            }
        }

        resp = self.client.search(index=self.collection_name, body=query)
        _id = self._get_id_from_resp(resp)
        self.client.delete(index=self.collection_name, id=_id)

    def update(self, vector_id=None, vectors=None, metadata=None):
        """
        Update a vector and its metadata.

        Args:
            vector_id (str): ID of the vector to update.
            vectors (List[float], optional): Updated vector.
            metadata (Dict, optional): Updated metadata.
        """
        # TODO None vector 
        query = {
            'query': {
                'term': {
                    'id': vector_id
                }
            }
        }

        resp = self.client.search(index=self.collection_name, body=query)
        _id = self._get_id_from_resp(resp)
        update_body = {
            'doc': {
                'id': vector_id,
                'vectors': vectors,
                'metadata': metadata,
            }
        }
        self.client.update(index=self.collection_name, id=_id, body=update_body)

    def get(self, vector_id):
        """
        Retrieve a vector by ID.

        Args:
            vector_id (str): ID of the vector to retrieve.

        Returns:
            OutputData: Retrieved vector.
        """
        query = {
            'query': {
                'term': {
                    'id': vector_id
                }
            }
        }
        
        resp = self.client.search(index=self.collection_name, body=query)
        _id = self._get_id_from_resp(resp)
        result = self.client.get(index=self.collection_name, id=_id)
        output = self._parse_output([result])
        return output[0]

    def list_cols(self):
        """
        List all collections.

        Returns:
            List[dict]: List of collection.
        """
        return self.client.indices.get_alias("*")

    def delete_col(self):
        """Delete a collection."""
        return self.client.indices.delete(index=self.collection_name)

    def col_info(self):
        """
        Get information about a collection.

        Returns:
            Dict[str, Any]: Collection information.
        """
        return self.client.indices.get(index=self.collection_name)

    def list(self, filters: dict = None, limit: int = 100) -> list:
        """
        List all vectors in a collection.

        Args:
            filters (Dict, optional): Filters to apply to the list.
            limit (int, optional): Number of vectors to return. Defaults to 100.

        Returns:
            List[OutputData]: List of vectors.
        """
        query_filter = self._create_filter(filters) if filters else None
        query = {
            'query': {
                'bool': {
                    'filter': {
                        'term': query_filter
                    }
                }
            },
            'size': limit
        }
        response = self.client.search(index=self.collection_name, body=query)
        result = self._parse_output(response['hits']['hits'])
        return result
    