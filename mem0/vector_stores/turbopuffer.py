import logging
import os
from typing import Any, Dict, List, Optional, Union

try:
    from turbopuffer import Turbopuffer as TurbopufferClient
except ImportError:
    raise ImportError(
        "Turbopuffer requires extra dependencies. Install with `pip install turbopuffer`"
    ) from None

from pydantic import BaseModel

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: Optional[str]
    score: Optional[float]
    payload: Optional[Dict]


class TurbopufferDB(VectorStoreBase):
    def __init__(
        self,
        collection_name: str,
        embedding_model_dims: int,
        api_key: Optional[str] = None,
        region: str = "gcp-us-central1",
        distance_metric: str = "cosine_distance",
        batch_size: int = 100,
        extra_params: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the Turbopuffer vector store.

        Args:
            collection_name (str): Name of the namespace/collection.
            embedding_model_dims (int): Dimensions of the embedding model.
            api_key (str, optional): API key for Turbopuffer. Defaults to None.
            region (str, optional): Turbopuffer region. Defaults to "gcp-us-central1".
            distance_metric (str, optional): Distance metric for vector similarity.
                Options: "cosine_distance" or "euclidean_squared". Defaults to "cosine_distance".
            batch_size (int, optional): Batch size for operations. Defaults to 100.
            extra_params (Dict, optional): Additional parameters for Turbopuffer client. Defaults to None.
        """
        api_key = api_key or os.environ.get("TURBOPUFFER_API_KEY")
        if not api_key:
            raise ValueError(
                "Turbopuffer API key must be provided either as a parameter or via TURBOPUFFER_API_KEY environment variable"
            )

        params = extra_params or {}
        params["region"] = region

        self.client = TurbopufferClient(api_key=api_key, **params)
        self.collection_name = collection_name
        self.embedding_model_dims = embedding_model_dims
        self.distance_metric = distance_metric
        self.batch_size = batch_size

        self.namespace = self.client.namespace(self.collection_name)

    def create_col(self, name=None, vector_size=None, distance=None):
        """
        Create a new namespace in Turbopuffer.
        Namespaces are created implicitly on first upsert, so this is a no-op.
        """
        pass

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

        if ids is None:
            ids = [str(i) for i in range(len(vectors))]

        for i in range(0, len(vectors), self.batch_size):
            batch_end = i + self.batch_size
            rows = []
            for j in range(i, min(batch_end, len(vectors))):
                row = {}
                if payloads and payloads[j]:
                    row.update(payloads[j])
                row["id"] = str(ids[j])
                row["vector"] = vectors[j]
                rows.append(row)

            self.namespace.write(
                upsert_rows=rows,
                distance_metric=self.distance_metric,
            )

    def _parse_output(self, rows) -> List[OutputData]:
        """
        Parse the output data from Turbopuffer query results.

        Args:
            rows: List of Row objects from Turbopuffer query.

        Returns:
            List[OutputData]: Parsed output data.
        """
        results = []
        for row in rows:
            row_dict = row.model_dump()
            row_id = str(row_dict.pop("id"))
            dist = row_dict.pop("$dist", None)
            row_dict.pop("vector", None)

            score = 1 - dist if dist is not None else None

            results.append(OutputData(
                id=row_id,
                score=score,
                payload=row_dict,
            ))
        return results

    def _convert_filters(self, filters: Optional[Dict]):
        """
        Convert mem0 filters to Turbopuffer filter format.

        Turbopuffer filters use tuple format: ("And", (("field", "Op", value), ...))
        """
        if not filters:
            return None

        conditions = []
        for key, value in filters.items():
            if isinstance(value, dict):
                if "gte" in value:
                    conditions.append((key, "Gte", value["gte"]))
                if "lte" in value:
                    conditions.append((key, "Lte", value["lte"]))
            else:
                conditions.append((key, "Eq", value))

        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return ("And", tuple(conditions))

    def search(
        self, query: str, vectors: List[float], limit: int = 5, filters: Optional[Dict] = None
    ) -> List[OutputData]:
        """
        Search for similar vectors.

        Args:
            query (str): Query text (unused in vector search, kept for interface consistency).
            vectors (list): Query vector to search with.
            limit (int, optional): Number of results to return. Defaults to 5.
            filters (dict, optional): Filters to apply to the search. Defaults to None.

        Returns:
            list: Search results.
        """
        query_params = {
            "rank_by": ("vector", "ANN", vectors),
            "top_k": limit,
            "include_attributes": True,
        }

        tpuf_filters = self._convert_filters(filters)
        if tpuf_filters is not None:
            query_params["filters"] = tpuf_filters

        response = self.namespace.query(**query_params)
        return self._parse_output(response.rows or [])

    def delete(self, vector_id: Union[str, int]):
        """
        Delete a vector by ID.

        Args:
            vector_id (Union[str, int]): ID of the vector to delete.
        """
        self.namespace.write(deletes=[str(vector_id)])

    def update(
        self,
        vector_id: Union[str, int],
        vector: Optional[List[float]] = None,
        payload: Optional[Dict] = None,
    ):
        """
        Update a vector and its payload.

        Args:
            vector_id (Union[str, int]): ID of the vector to update.
            vector (list, optional): Updated vector. Defaults to None.
            payload (dict, optional): Updated payload. Defaults to None.
        """
        if vector is not None:
            row = {}
            if payload:
                row.update(payload)
            row["id"] = str(vector_id)
            row["vector"] = vector
            self.namespace.write(
                upsert_rows=[row],
                distance_metric=self.distance_metric,
            )
        elif payload is not None:
            row = dict(payload)
            row["id"] = str(vector_id)
            self.namespace.write(patch_rows=[row])

    def get(self, vector_id: Union[str, int]) -> Optional[OutputData]:
        """
        Retrieve a vector by ID.

        Args:
            vector_id (Union[str, int]): ID of the vector to retrieve.

        Returns:
            OutputData: Retrieved vector data, or None if not found.
        """
        try:
            response = self.namespace.query(
                top_k=1,
                rank_by=("vector", "ANN", [0.0] * self.embedding_model_dims),
                filters=("id", "Eq", str(vector_id)),
                include_attributes=True,
            )
            rows = response.rows or []
            if rows:
                return self._parse_output(rows)[0]
            return None
        except Exception as e:
            logger.error(f"Error retrieving vector {vector_id}: {e}")
            return None

    def list_cols(self) -> list:
        """
        List all namespaces.

        Returns:
            list: List of namespace summaries.
        """
        try:
            result = []
            for ns in self.client.namespaces():
                result.append(ns)
            return result
        except Exception as e:
            logger.error(f"Error listing namespaces: {e}")
            return []

    def delete_col(self):
        """Delete the entire namespace."""
        try:
            self.namespace.delete_all()
            logger.info(f"Namespace {self.collection_name} deleted successfully")
        except Exception as e:
            logger.error(f"Error deleting namespace {self.collection_name}: {e}")

    def col_info(self) -> Dict:
        """
        Get information about the namespace.

        Returns:
            dict: Namespace metadata.
        """
        try:
            metadata = self.namespace.metadata()
            return {
                "name": self.collection_name,
                "approx_row_count": metadata.approx_row_count,
                "approx_logical_bytes": metadata.approx_logical_bytes,
                "created_at": str(metadata.created_at),
                "updated_at": str(metadata.updated_at),
            }
        except Exception:
            return {"name": self.collection_name}

    def list(self, filters: Optional[Dict] = None, limit: int = 100) -> list:
        """
        List vectors in the namespace with optional filtering.

        Args:
            filters (dict, optional): Filters to apply. Defaults to None.
            limit (int, optional): Number of vectors to return. Defaults to 100.

        Returns:
            list: Wrapped list of OutputData objects ([[results]]).
        """
        query_params = {
            "rank_by": ("vector", "ANN", [0.0] * self.embedding_model_dims),
            "top_k": limit,
            "include_attributes": True,
        }

        tpuf_filters = self._convert_filters(filters)
        if tpuf_filters is not None:
            query_params["filters"] = tpuf_filters

        try:
            response = self.namespace.query(**query_params)
            results = self._parse_output(response.rows or [])
        except Exception as e:
            logger.error(f"Error listing vectors: {e}")
            results = []
        return [results]

    def count(self) -> int:
        """
        Get approximate count of vectors in the namespace.

        Returns:
            int: Approximate number of vectors.
        """
        try:
            metadata = self.namespace.metadata()
            return metadata.approx_row_count
        except Exception:
            return 0

    def reset(self):
        """Reset the namespace by deleting all vectors."""
        self.delete_col()
