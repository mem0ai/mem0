import logging
import uuid
from typing import List, Optional

from pydantic import BaseModel

try:
    import vecs
except ImportError:
    raise ImportError("The 'vecs' library is required. Please install it using 'pip install vecs'.")

from mem0.vector_stores.base import VectorStoreBase
from mem0.configs.vector_stores.supabase import IndexMethod, IndexMeasure

logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: Optional[str]
    score: Optional[float]
    payload: Optional[dict]


class Supabase(VectorStoreBase):
    def __init__(
        self,
        connection_string: str,
        collection_name: str,
        embedding_model_dims: int,
        index_method: IndexMethod = IndexMethod.AUTO,
        index_measure: IndexMeasure = IndexMeasure.COSINE,
    ):
        """
        Initialize the Supabase vector store using vecs.

        Args:
            connection_string (str): PostgreSQL connection string
            collection_name (str): Collection name
            embedding_model_dims (int): Dimension of the embedding vector
            index_method (IndexMethod): Index method to use. Defaults to AUTO.
            index_measure (IndexMeasure): Distance measure to use. Defaults to COSINE.
        """
        self.db = vecs.create_client(connection_string)
        self.collection_name = collection_name
        self.embedding_model_dims = embedding_model_dims
        self.index_method = index_method
        self.index_measure = index_measure

        collections = self.list_cols()
        if collection_name not in collections:
            self.create_col(embedding_model_dims)

    def _preprocess_filters(self, filters: Optional[dict] = None) -> Optional[dict]:
        """
        Preprocess filters to be compatible with vecs.

        Args:
            filters (Dict, optional): Filters to preprocess. Multiple filters will be
                combined with AND logic.
        """
        if filters is None:
            return None

        if len(filters) == 1:
            # For single filter, keep the simple format
            key, value = next(iter(filters.items()))
            return {key: {"$eq": value}}

        # For multiple filters, use $and clause
        return {"$and": [{key: {"$eq": value}} for key, value in filters.items()]}

    def create_col(self, embedding_model_dims: Optional[int] = None) -> None:
        """
        Create a new collection with vector support.
        Will also initialize vector search index.

        Args:
            embedding_model_dims (int, optional): Dimension of the embedding vector.
                If not provided, uses the dimension specified in initialization.
        """
        dims = embedding_model_dims or self.embedding_model_dims
        if not dims:
            raise ValueError(
                "embedding_model_dims must be provided either during initialization or when creating collection"
            )

        logger.info(f"Creating new collection: {self.collection_name}")
        try:
            self.collection = self.db.get_or_create_collection(name=self.collection_name, dimension=dims)
            self.collection.create_index(method=self.index_method.value, measure=self.index_measure.value)
            logger.info(f"Successfully created collection {self.collection_name} with dimension {dims}")
        except Exception as e:
            logger.error(f"Failed to create collection: {str(e)}")
            raise

    def insert(
        self, vectors: List[List[float]], payloads: Optional[List[dict]] = None, ids: Optional[List[str]] = None
    ):
        """
        Insert vectors into the collection.

        Args:
            vectors (List[List[float]]): List of vectors to insert
            payloads (List[Dict], optional): List of payloads corresponding to vectors
            ids (List[str], optional): List of IDs corresponding to vectors
        """
        logger.info(f"Inserting {len(vectors)} vectors into collection {self.collection_name}")

        if not ids:
            ids = [str(uuid.uuid4()) for _ in vectors]
        if not payloads:
            payloads = [{} for _ in vectors]

        records = [(id, vector, payload) for id, vector, payload in zip(ids, vectors, payloads)]
        print(records)

        self.collection.upsert(records)

    def search(self, query: List[float], limit: int = 5, filters: Optional[dict] = None) -> List[OutputData]:
        """
        Search for similar vectors.

        Args:
            query (List[float]): Query vector
            limit (int, optional): Number of results to return. Defaults to 5.
            filters (Dict, optional): Filters to apply to the search. Defaults to None.

        Returns:
            List[OutputData]: Search results
        """
        filters = self._preprocess_filters(filters)
        print(filters)
        results = self.collection.query(
            data=query, limit=limit, filters=filters, include_metadata=True, include_value=True
        )
        print(results)

        return [OutputData(id=str(result[0]), score=float(result[1]), payload=result[2]) for result in results]

    def delete(self, vector_id: str):
        """
        Delete a vector by ID.

        Args:
            vector_id (str): ID of the vector to delete
        """
        self.collection.delete([(vector_id,)])

    def update(self, vector_id: str, vector: Optional[List[float]] = None, payload: Optional[dict] = None):
        """
        Update a vector and/or its payload.

        Args:
            vector_id (str): ID of the vector to update
            vector (List[float], optional): Updated vector
            payload (Dict, optional): Updated payload
        """
        if vector is None:
            # If only updating metadata, we need to get the existing vector
            existing = self.get(vector_id)
            if existing and existing.payload:
                vector = existing.payload.get("vector", [])

        if vector:
            self.collection.upsert([(vector_id, vector, payload or {})])

    def get(self, vector_id: str) -> Optional[OutputData]:
        """
        Retrieve a vector by ID.

        Args:
            vector_id (str): ID of the vector to retrieve

        Returns:
            Optional[OutputData]: Retrieved vector data or None if not found
        """
        result = self.collection.fetch([(vector_id,)])
        if not result:
            return []

        record = result[0]
        return OutputData(id=str(record.id), score=None, payload=record.metadata)

    def list_cols(self) -> List[str]:
        """
        List all collections.

        Returns:
            List[str]: List of collection names
        """
        return self.db.list_collections()

    def delete_col(self):
        """Delete the collection."""
        self.db.delete_collection(self.collection_name)

    def col_info(self) -> dict:
        """
        Get information about the collection.

        Returns:
            Dict: Collection information including name and configuration
        """
        info = self.collection.describe()
        return {
            "name": info.name,
            "count": info.vectors,
            "dimension": info.dimension,
            "index": {"method": info.index_method, "metric": info.distance_metric},
        }

    def list(self, filters: Optional[dict] = None, limit: int = 100) -> List[OutputData]:
        """
        List vectors in the collection.

        Args:
            filters (Dict, optional): Filters to apply
            limit (int, optional): Maximum number of results to return. Defaults to 100.

        Returns:
            List[OutputData]: List of vectors
        """
        filters = self._preprocess_filters(filters)
        query = [0] * self.embedding_model_dims
        ids = self.collection.query(
            data=query, limit=limit, filters=filters, include_metadata=True, include_value=False
        )
        ids = [id[0] for id in ids]
        records = self.collection.fetch(ids=ids)

        return [[OutputData(id=str(record[0]), score=None, payload=record[2]) for record in records]]
