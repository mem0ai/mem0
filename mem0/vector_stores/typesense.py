import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

try:
    import typesense
except ImportError:
    raise ImportError(
        "Typesense vector store requires typesense. "
        "Please install it using 'pip install typesense'"
    )

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: Optional[str]
    score: Optional[float]
    payload: Optional[dict]


class TypesenseDB(VectorStoreBase):
    def __init__(
        self,
        host: str = "localhost",
        port: int = 8108,
        protocol: str = "http",
        api_key: str = "xyz",
        collection_name: str = "memories",
        embedding_model_dims: int = 1536,
        **kwargs
    ):
        """
        Initialize the Typesense vector store.

        Args:
            host (str): Typesense server host
            port (int): Typesense server port
            protocol (str): Connection protocol (http/https)
            api_key (str): API key for authentication
            collection_name (str): Collection name for storing vectors
            embedding_model_dims (int): Dimension of the embedding vector
            **kwargs: Additional arguments passed to Typesense client
        """
        self.host = host
        self.port = port
        self.protocol = protocol
        self.api_key = api_key
        self.collection_name = collection_name
        self.embedding_model_dims = embedding_model_dims
        self.kwargs = kwargs

        # Initialize Typesense client
        self.client = None
        self._setup_connection()
        
        # Create collection if it doesn't exist
        self._create_collection()

    def _setup_connection(self):
        """Setup Typesense connection."""
        try:
            self.client = typesense.Client({
                'nodes': [{
                    'host': self.host,
                    'port': self.port,
                    'protocol': self.protocol
                }],
                'api_key': self.api_key,
                'connection_timeout_seconds': 2
            })
            logger.info(f"Successfully connected to Typesense at {self.protocol}://{self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to connect to Typesense: {e}")
            raise

    def _create_collection(self):
        """Create collection if it doesn't exist."""
        try:
            # Check if collection exists
            collections = self.client.collections.retrieve()
            collection_names = [col['name'] for col in collections]
            
            if self.collection_name not in collection_names:
                # Create collection with vector field
                schema = {
                    "name": self.collection_name,
                    "fields": [
                        {"name": "id", "type": "string"},
                        {"name": "vector", "type": "float[]", "embed": {
                            "from": ["text"],
                            "model_config": {
                                "model_name": "ts/all-MiniLM-L11-v1",
                                "dimension": self.embedding_model_dims
                            }
                        }},
                        {"name": "payload", "type": "string"},
                        {"name": "text", "type": "string"}
                    ],
                    "default_sorting_field": "id"
                }
                
                self.client.collections.create(schema)
                logger.info(f"Created collection '{self.collection_name}' with vector dimension {self.embedding_model_dims}")
            else:
                logger.info(f"Collection '{self.collection_name}' already exists")
        except Exception as e:
            logger.error(f"Failed to create collection: {e}")
            raise

    def create_col(self, name: str = None, vector_size: int = None, distance: str = "cosine"):
        """
        Create a new collection.

        Args:
            name (str, optional): Collection name (uses self.collection_name if not provided)
            vector_size (int, optional): Vector dimension (uses self.embedding_model_dims if not provided)
            distance (str): Distance metric (cosine, euclidean, dot_product)
        """
        collection_name = name or self.collection_name
        dims = vector_size or self.embedding_model_dims

        try:
            # Check if collection exists
            collections = self.client.collections.retrieve()
            collection_names = [col['name'] for col in collections]
            
            if collection_name in collection_names:
                logger.info(f"Collection '{collection_name}' already exists")
                return

            # Create collection with vector field
            schema = {
                "name": collection_name,
                "fields": [
                    {"name": "id", "type": "string"},
                    {"name": "vector", "type": "float[]", "embed": {
                        "from": ["text"],
                        "model_config": {
                            "model_name": "ts/all-MiniLM-L11-v1",
                            "dimension": dims
                        }
                    }},
                    {"name": "payload", "type": "string"},
                    {"name": "text", "type": "string"}
                ],
                "default_sorting_field": "id"
            }
            
            self.client.collections.create(schema)
            logger.info(f"Created collection '{collection_name}' with vector dimension {dims}")
        except Exception as e:
            logger.error(f"Failed to create collection: {e}")
            raise

    def insert(
        self,
        vectors: List[List[float]],
        payloads: Optional[List[Dict]] = None,
        ids: Optional[List[str]] = None
    ):
        """
        Insert vectors into the collection.

        Args:
            vectors (List[List[float]]): List of vectors to insert
            payloads (List[Dict], optional): List of payloads corresponding to vectors
            ids (List[str], optional): List of IDs corresponding to vectors
        """
        logger.info(f"Inserting {len(vectors)} vectors into collection {self.collection_name}")

        if payloads is None:
            payloads = [{}] * len(vectors)
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in range(len(vectors))]

        try:
            # Prepare documents for insertion
            documents = []
            for vector, payload, vec_id in zip(vectors, payloads, ids):
                documents.append({
                    "id": vec_id,
                    "vector": vector,
                    "payload": json.dumps(payload),
                    "text": payload.get("text", "")  # Required for embedding
                })

            # Insert documents
            self.client.collections[self.collection_name].documents.create_many(documents)
            logger.info(f"Successfully inserted {len(documents)} vectors")
        except Exception as e:
            logger.error(f"Failed to insert vectors: {e}")
            raise

    def search(
        self,
        query: str,
        vectors: List[float],
        limit: int = 5,
        filters: Optional[Dict] = None,
    ) -> List[OutputData]:
        """
        Search for similar vectors using vector similarity.

        Args:
            query (str): Query string for text search
            vectors (List[float]): Query vector for vector search
            limit (int): Number of results to return
            filters (Dict, optional): Filters to apply to the search

        Returns:
            List[OutputData]: Search results
        """
        try:
            # Build search parameters
            search_params = {
                'q': query,
                'vector_query': f'vector:({",".join(map(str, vectors))})',
                'per_page': limit,
                'sort_by': '_vector_distance:asc'
            }
            
            if filters:
                # Build filter expression
                filter_parts = []
                for key, value in filters.items():
                    if isinstance(value, str):
                        filter_parts.append(f'{key}:={value}')
                    else:
                        filter_parts.append(f'{key}:={value}')
                search_params['filter_by'] = ' && '.join(filter_parts)

            # Perform search
            results = self.client.collections[self.collection_name].documents.search(search_params)
            
            # Convert results to OutputData format
            output_results = []
            for hit in results['hits']:
                try:
                    payload = json.loads(hit['document']['payload']) if hit['document']['payload'] else {}
                except json.JSONDecodeError:
                    payload = {}
                
                # Calculate similarity score (1 - distance for cosine similarity)
                distance = hit.get('vector_distance', 0.0)
                score = 1 - distance if distance <= 1 else 0.0
                
                output_results.append(OutputData(
                    id=hit['document']['id'],
                    score=float(score),
                    payload=payload
                ))

            return output_results
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise

    def delete(self, vector_id: str):
        """
        Delete a vector by ID.

        Args:
            vector_id (str): ID of the vector to delete
        """
        try:
            self.client.collections[self.collection_name].documents[vector_id].delete()
            logger.info(f"Deleted vector with id: {vector_id}")
        except Exception as e:
            logger.error(f"Failed to delete vector: {e}")
            raise

    def update(
        self,
        vector_id: str,
        vector: Optional[List[float]] = None,
        payload: Optional[Dict] = None,
    ):
        """
        Update a vector and its payload.

        Args:
            vector_id (str): ID of the vector to update
            vector (List[float], optional): Updated vector
            payload (Dict, optional): Updated payload
        """
        try:
            # Get existing document to verify it exists
            self.client.collections[self.collection_name].documents[vector_id].retrieve()
            
            # Prepare update data
            update_data = {"id": vector_id}
            if vector is not None:
                update_data["vector"] = vector
            if payload is not None:
                update_data["payload"] = json.dumps(payload)
                update_data["text"] = payload.get("text", "")  # Required for embedding

            # Update document
            self.client.collections[self.collection_name].documents[vector_id].update(update_data)
            
            logger.info(f"Updated vector with id: {vector_id}")
        except Exception:
            logger.warning(f"Vector with id {vector_id} not found for update")
            return

    def get(self, vector_id: str) -> Optional[OutputData]:
        """
        Retrieve a vector by ID.

        Args:
            vector_id (str): ID of the vector to retrieve

        Returns:
            OutputData: Retrieved vector or None if not found
        """
        try:
            document = self.client.collections[self.collection_name].documents[vector_id].retrieve()
            
            try:
                payload = json.loads(document['payload']) if document['payload'] else {}
            except json.JSONDecodeError:
                payload = {}

            return OutputData(
                id=document['id'],
                score=None,
                payload=payload
            )
        except Exception as e:
            logger.error(f"Failed to get vector: {e}")
            return None

    def list_cols(self) -> List[str]:
        """
        List all collections.

        Returns:
            List[str]: List of collection names
        """
        try:
            collections = self.client.collections.retrieve()
            return [col['name'] for col in collections]
        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            return []

    def delete_col(self):
        """Delete the collection."""
        try:
            self.client.collections[self.collection_name].delete()
            logger.info(f"Deleted collection '{self.collection_name}'")
        except Exception as e:
            logger.error(f"Failed to delete collection: {e}")
            raise

    def col_info(self) -> Dict[str, Any]:
        """
        Get information about the collection.

        Returns:
            Dict[str, Any]: Collection information
        """
        try:
            collection = self.client.collections[self.collection_name].retrieve()
            
            return {
                "name": collection['name'],
                "num_documents": collection['num_documents'],
                "vector_dims": self.embedding_model_dims,
                "host": f"{self.protocol}://{self.host}:{self.port}"
            }
        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            return {}

    def list(
        self,
        filters: Optional[Dict] = None,
        limit: int = 100
    ) -> List[List[OutputData]]:
        """
        List all vectors in the collection.

        Args:
            filters (Dict, optional): Filters to apply
            limit (int): Number of vectors to return

        Returns:
            List[List[OutputData]]: List of vectors
        """
        try:
            # Build search parameters
            search_params = {
                'q': '*',
                'per_page': limit
            }
            
            if filters:
                # Build filter expression
                filter_parts = []
                for key, value in filters.items():
                    if isinstance(value, str):
                        filter_parts.append(f'{key}:={value}')
                    else:
                        filter_parts.append(f'{key}:={value}')
                search_params['filter_by'] = ' && '.join(filter_parts)

            # Perform search
            results = self.client.collections[self.collection_name].documents.search(search_params)
            
            output_results = []
            for hit in results['hits']:
                try:
                    payload = json.loads(hit['document']['payload']) if hit['document']['payload'] else {}
                except json.JSONDecodeError:
                    payload = {}

                output_results.append(OutputData(
                    id=hit['document']['id'],
                    score=None,
                    payload=payload
                ))

            return [output_results]
        except Exception as e:
            logger.error(f"Failed to list vectors: {e}")
            return [[]]

    def reset(self):
        """Reset the collection by deleting and recreating it."""
        try:
            logger.warning(f"Resetting collection {self.collection_name}...")
            self.delete_col()
            self._create_collection()
            logger.info(f"Collection '{self.collection_name}' has been reset")
        except Exception as e:
            logger.error(f"Failed to reset collection: {e}")
            raise

    def __del__(self):
        """Cleanup when the object is deleted."""
        try:
            if self.client:
                # Typesense client doesn't require explicit cleanup
                pass
        except Exception:
            pass
