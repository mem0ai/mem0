import logging
import os
from typing import Any, Dict, List, Optional, Union

try:
    import turbopuffer as tpuf
except ImportError:
    raise ImportError(
        "Turbopuffer requires extra dependencies. Install with `pip install turbopuffer`"
    ) from None

from pydantic import BaseModel

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: Optional[str]  # memory id
    score: Optional[float]  # distance
    payload: Optional[Dict]  # metadata


class TurbopufferDB(VectorStoreBase):
    def __init__(
        self,
        collection_name: str,
        embedding_model_dims: int,
        client: Optional["tpuf.Namespace"] = None,
        api_key: Optional[str] = None,
        api_base_url: Optional[str] = None,
        distance_metric: str = "cosine_distance",
        batch_size: int = 100,
        extra_params: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the Turbopuffer vector store.

        Args:
            collection_name (str): Name of the namespace/collection.
            embedding_model_dims (int): Dimensions of the embedding model.
            client (Namespace, optional): Existing Turbopuffer Namespace instance. Defaults to None.
            api_key (str, optional): API key for Turbopuffer. Defaults to None.
            api_base_url (str, optional): API base URL for Turbopuffer. Defaults to None.
            distance_metric (str, optional): Distance metric for vector similarity. 
                Options: "cosine_distance" or "euclidean_distance". Defaults to "cosine_distance".
            batch_size (int, optional): Batch size for operations. Defaults to 100.
            extra_params (Dict, optional): Additional parameters for Turbopuffer client. Defaults to None.
        """
        if client:
            self.namespace = client
        else:
            api_key = api_key or os.environ.get("TURBOPUFFER_API_KEY")
            if not api_key:
                raise ValueError(
                    "Turbopuffer API key must be provided either as a parameter or as an environment variable"
                )

            # Configure the client
            tpuf.api_key = api_key
            if api_base_url:
                tpuf.api_base_url = api_base_url

        self.collection_name = collection_name
        self.embedding_model_dims = embedding_model_dims
        self.distance_metric = distance_metric
        self.batch_size = batch_size

        # Initialize the namespace
        self.namespace = tpuf.Namespace(self.collection_name)

    def create_col(self):
        """
        Create a new namespace in Turbopuffer.
        Note: In Turbopuffer, namespaces are created implicitly on first upsert.
        """
        logger.info(f"Turbopuffer namespace will be created on first upsert: {self.collection_name}")

    def insert(
        self,
        vectors: List[List[float]],
        payloads: Optional[List[Dict]] = None,
        ids: Optional[List[Union[str, int]]] = None,
    ):
        """
        Insert vectors into the namespace.

        Args:
            vectors (list): List of vectors to insert.
            payloads (list, optional): List of payloads corresponding to vectors. Defaults to None.
            ids (list, optional): List of IDs corresponding to vectors. Defaults to None.
        """
        logger.info(f"Inserting {len(vectors)} vectors into namespace {self.collection_name}")

        # Convert payloads to Turbopuffer's attribute format
        attributes = None
        if payloads:
            attributes = {}
            for i, payload in enumerate(payloads):
                for key, value in payload.items():
                    if key not in attributes:
                        attributes[key] = [None] * len(payloads)
                    attributes[key][i] = value

        # Generate IDs if not provided
        if ids is None:
            ids = [str(i) for i in range(len(vectors))]

        # Upsert in batches
        for i in range(0, len(vectors), self.batch_size):
            batch_ids = ids[i:i + self.batch_size]
            batch_vectors = vectors[i:i + self.batch_size]
            batch_attributes = {k: v[i:i + self.batch_size] for k, v in attributes.items()} if attributes else None

            self.namespace.upsert(
                ids=batch_ids,
                vectors=batch_vectors,
                attributes=batch_attributes,
                distance_metric=self.distance_metric
            )

    def _parse_output(self, matches: List[Dict]) -> List[OutputData]:
        """
        Parse the output data from Turbopuffer search results.

        Args:
            matches (List[Dict]): Output data from Turbopuffer query.

        Returns:
            List[OutputData]: Parsed output data.
        """
        results = []
        for match in matches:
            # Convert score to similarity (higher is better)
            score = 1 - match.get('distance', 0) if 'distance' in match else None
            
            entry = OutputData(
                id=match.get('id'),
                score=score,
                payload=match.get('attributes', {}),
            )
            results.append(entry)
        return results

    def _convert_filters(self, filters: Optional[Dict]) -> Optional[List]:
        """
        Convert mem0 filters to Turbopuffer filter format.
        
        Turbopuffer filters use format: ['And', [['field', 'Op', value], ...]]
        """
        if not filters:
            return None
            
        conditions = []
        for key, value in filters.items():
            if isinstance(value, dict):
                if 'gte' in value and 'lte' in value:
                    conditions.append([key, 'Gte', value['gte']])
                    conditions.append([key, 'Lte', value['lte']])
                elif 'gte' in value:
                    conditions.append([key, 'Gte', value['gte']])
                elif 'lte' in value:
                    conditions.append([key, 'Lte', value['lte']])
            else:
                conditions.append([key, 'Eq', value])
        
        return ['And', conditions] if conditions else None

    def search(
        self, query: str, vectors: List[float], limit: int = 5, filters: Optional[Dict] = None
    ) -> List[OutputData]:
        """
        Search for similar vectors.

        Args:
            query (str): Query text (unused in vector search, but kept for interface consistency).
            vectors (list): Query vector to search with.
            limit (int, optional): Number of results to return. Defaults to 5.
            filters (dict, optional): Filters to apply to the search. Defaults to None.

        Returns:
            list: Search results.
        """
        turbopuffer_filters = self._convert_filters(filters)
        
        results = self.namespace.query(
            vector=vectors,
            top_k=limit,
            distance_metric=self.distance_metric,
            filters=turbopuffer_filters,
            include_attributes=True
        )
        
        return self._parse_output(results)

    def delete(self, vector_id: Union[str, int]):
        """
        Delete a vector by ID.

        Args:
            vector_id (Union[str, int]): ID of the vector to delete.
        """
        self.namespace.delete(ids=[str(vector_id)])

    def update(
        self, 
        vector_id: Union[str, int], 
        vector: Optional[List[float]] = None, 
        payload: Optional[Dict] = None
    ):
        """
        Update a vector and its payload.

        Args:
            vector_id (Union[str, int]): ID of the vector to update.
            vector (list, optional): Updated vector. Defaults to None.
            payload (dict, optional): Updated payload. Defaults to None.
        """
        attributes = payload if payload else None
        self.namespace.upsert(
            ids=[str(vector_id)],
            vectors=[vector] if vector else None,
            attributes=attributes,
            distance_metric=self.distance_metric
        )

    def get(self, vector_id: Union[str, int]) -> OutputData:
        """
        Retrieve a vector by ID.

        Args:
            vector_id (Union[str, int]): ID of the vector to retrieve.

        Returns:
            OutputData: Retrieved vector or None if not found.
        """
        try:
            # Turbopuffer doesn't have a direct fetch API, so we use query with exact match filter
            results = self.namespace.query(
                vector=[0.0] * self.embedding_model_dims,  # Dummy vector
                top_k=1,
                filters=['And', [['id', 'Eq', str(vector_id)]]],
                include_attributes=True
            )
            
            if results:
                return self._parse_output(results)[0]
            return None
        except Exception as e:
            logger.error(f"Error retrieving vector {vector_id}: {e}")
            return None

    def list_cols(self):
        """
        List all namespaces.
        Note: Turbopuffer doesn't currently have a namespace listing API.
        """
        logger.warning("Turbopuffer doesn't support listing namespaces through the API")
        return []

    def delete_col(self):
        """Delete the entire namespace."""
        try:
            # Delete all vectors in the namespace
            self.namespace.delete(filters=['And', []])
            logger.info(f"All vectors in namespace {self.collection_name} deleted successfully")
        except Exception as e:
            logger.error(f"Error deleting namespace {self.collection_name}: {e}")

    def col_info(self) -> Dict:
        """
        Get information about the namespace.
        Note: Turbopuffer doesn't provide detailed namespace info.
        """
        return {
            "name": self.collection_name,
            "dimensions": self.embedding_model_dims,
            "distance_metric": self.distance_metric
        }

    def list(self, filters: Optional[Dict] = None, limit: int = 100) -> List[OutputData]:
        """
        List vectors in the namespace with optional filtering.

        Args:
            filters (dict, optional): Filters to apply to the list. Defaults to None.
            limit (int, optional): Number of vectors to return. Defaults to 100.

        Returns:
            List[OutputData]: List of vectors with their metadata.
        """
        turbopuffer_filters = self._convert_filters(filters)
        
        results = self.namespace.query(
            vector=[0.0] * self.embedding_model_dims,  # Dummy vector
            top_k=limit,
            distance_metric=self.distance_metric,
            filters=turbopuffer_filters,
            include_attributes=True
        )
        
        return self._parse_output(results)

    def count(self) -> int:
        """
        Count number of vectors in the namespace.
        Note: Turbopuffer doesn't provide a direct count API.
        """
        # Get approximate count by querying with a large limit
        results = self.namespace.query(
            vector=[0.0] * self.embedding_model_dims,
            top_k=10000,  # Max practical limit
            include_attributes=False
        )
        return len(results)

    def reset(self):
        """
        Reset the namespace by deleting all vectors.
        """
        self.delete_col()