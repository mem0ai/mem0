import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel

try:
    from azure.cosmos import CosmosClient, PartitionKey
    from azure.cosmos.exceptions import CosmosResourceNotFoundError
except ImportError:
    raise ImportError("Azure Cosmos DB requires extra dependencies. Install with `pip install azure-cosmos`") from None

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)

VALID_FILTER_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class OutputData(BaseModel):
    id: Optional[str]  # memory id
    score: Optional[float]  # similarity score (higher = more similar)
    payload: Optional[Dict]  # metadata


class AzureCosmosNoSQL(VectorStoreBase):
    def __init__(
        self,
        collection_name: str,
        database_name: str,
        embedding_model_dims: int,
        client: Optional["CosmosClient"] = None,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        connection_string: Optional[str] = None,
        metric: str = "cosine",
        index_type: str = "diskANN",
    ):
        """
        Initialize the Azure Cosmos DB for NoSQL vector store.

        Args:
            collection_name (str): Name of the container.
            database_name (str): Name of the database.
            embedding_model_dims (int): Dimensions of the embedding model.
            client (CosmosClient, optional): Existing Cosmos client instance. Defaults to None.
            endpoint (str, optional): Cosmos DB account endpoint URL. Defaults to None.
            api_key (str, optional): Cosmos DB account key. Defaults to None.
            connection_string (str, optional): Cosmos DB connection string. Defaults to None.
            metric (str, optional): Distance function ('cosine', 'dotproduct', 'euclidean'). Defaults to "cosine".
            index_type (str, optional): Vector index type ('flat', 'quantizedFlat', 'diskANN'). Defaults to "diskANN".
        """
        if client:
            self.client = client
        else:
            connection_string = connection_string or os.environ.get("AZURE_COSMOS_CONNECTION_STRING")
            if connection_string:
                self.client = CosmosClient.from_connection_string(connection_string)
            else:
                endpoint = endpoint or os.environ.get("AZURE_COSMOS_ENDPOINT")
                api_key = api_key or os.environ.get("AZURE_COSMOS_KEY")
                if not endpoint or not api_key:
                    raise ValueError(
                        "Azure Cosmos DB credentials must be provided: either a 'client', a "
                        "'connection_string', or 'endpoint' + 'api_key' (also settable via the "
                        "AZURE_COSMOS_CONNECTION_STRING or AZURE_COSMOS_ENDPOINT/AZURE_COSMOS_KEY "
                        "environment variables)."
                    )
                self.client = CosmosClient(url=endpoint, credential=api_key)

        self.collection_name = collection_name
        self.database_name = database_name
        self.embedding_model_dims = embedding_model_dims
        self.metric = metric
        self.index_type = index_type

        self.create_col(embedding_model_dims, metric)

    def create_col(self, vector_size: int, metric: str = "cosine"):
        """
        Create the database and container with a vector embedding/indexing policy.

        Args:
            vector_size (int): Size of the vectors to be stored.
            metric (str, optional): Distance function for vector similarity. Defaults to "cosine".
        """
        self.database = self.client.create_database_if_not_exists(id=self.database_name)

        vector_embedding_policy = {
            "vectorEmbeddings": [
                {
                    "path": "/vector",
                    "dataType": "float32",
                    "distanceFunction": metric,
                    "dimensions": vector_size,
                }
            ]
        }
        indexing_policy = {
            "indexingMode": "consistent",
            "includedPaths": [{"path": "/*"}],
            "excludedPaths": [{"path": '/"_etag"/?'}, {"path": "/vector/*"}],
            "vectorIndexes": [{"path": "/vector", "type": self.index_type}],
        }

        self.container = self.database.create_container_if_not_exists(
            id=self.collection_name,
            partition_key=PartitionKey(path="/id"),
            indexing_policy=indexing_policy,
            vector_embedding_policy=vector_embedding_policy,
        )

    def insert(
        self,
        vectors: List[List[float]],
        payloads: Optional[List[Dict]] = None,
        ids: Optional[List[Union[str, int]]] = None,
    ):
        """
        Insert vectors into the container.

        Args:
            vectors (list): List of vectors to insert.
            payloads (list, optional): List of payloads corresponding to vectors. Defaults to None.
            ids (list, optional): List of IDs corresponding to vectors. Defaults to None.
        """
        logger.info(f"Inserting {len(vectors)} vectors into container {self.collection_name}")
        for idx, vector in enumerate(vectors):
            item_id = str(ids[idx]) if ids is not None else str(idx)
            payload = payloads[idx] if payloads else {}
            self.container.upsert_item({"id": item_id, "vector": vector, "payload": payload})

    def _to_similarity(self, value: float) -> float:
        """Convert a VectorDistance() result into a similarity score (higher = better)."""
        if value is None:
            return None
        if self.metric == "euclidean":
            # Euclidean is a distance (lower = better): map [0, inf) -> (0, 1].
            return 1.0 / (1.0 + value)
        if self.metric == "cosine":
            # Cosmos returns cosine similarity in [-1, 1]: clamp to [0, 1].
            return max(0.0, min(1.0, value))
        # dotproduct: already higher = better.
        return value

    def _build_where(self, filters: Optional[Dict]) -> Tuple[str, List[Dict[str, Any]]]:
        """Build a parameterized WHERE clause from mem0 filters."""
        if not filters:
            return "", []

        clauses = []
        parameters = []
        for idx, (key, value) in enumerate(filters.items()):
            if not VALID_FILTER_KEY.match(key):
                raise ValueError(f"Invalid filter key: {key!r}")
            field = f'c.payload["{key}"]'
            if isinstance(value, dict) and ("gte" in value or "lte" in value):
                if "gte" in value:
                    clauses.append(f"{field} >= @p{idx}_gte")
                    parameters.append({"name": f"@p{idx}_gte", "value": value["gte"]})
                if "lte" in value:
                    clauses.append(f"{field} <= @p{idx}_lte")
                    parameters.append({"name": f"@p{idx}_lte", "value": value["lte"]})
            else:
                clauses.append(f"{field} = @p{idx}")
                parameters.append({"name": f"@p{idx}", "value": value})

        return " WHERE " + " AND ".join(clauses), parameters

    def search(
        self, query: str, vectors: List[float], top_k: int = 5, filters: Optional[Dict] = None
    ) -> List[OutputData]:
        """
        Search for similar vectors using VectorDistance().

        Args:
            query (str): Query text (unused; similarity is computed from `vectors`).
            vectors (list): Query vector.
            top_k (int, optional): Number of results to return. Defaults to 5.
            filters (dict, optional): Filters to apply to the search. Defaults to None.

        Returns:
            list: Search results.
        """
        where_clause, parameters = self._build_where(filters)
        # Pass the distance function explicitly instead of relying on the container's
        # embedding policy default. self.metric is validated against a fixed enum.
        distance_expr = f"VectorDistance(c.vector, @embedding, false, {{'distanceFunction': '{self.metric}', 'dataType': 'float32'}})"
        sql = (
            f"SELECT TOP @top_k c.id, c.payload, {distance_expr} AS distance "
            f"FROM c{where_clause} ORDER BY {distance_expr}"
        )
        parameters.extend(
            [
                {"name": "@top_k", "value": top_k},
                {"name": "@embedding", "value": vectors},
            ]
        )

        items = self.container.query_items(query=sql, parameters=parameters, enable_cross_partition_query=True)
        return [
            OutputData(
                id=item.get("id"),
                score=self._to_similarity(item.get("distance")),
                payload=item.get("payload"),
            )
            for item in items
        ]

    def delete(self, vector_id: Union[str, int]):
        """
        Delete a vector by ID.

        Args:
            vector_id (Union[str, int]): ID of the vector to delete.
        """
        try:
            self.container.delete_item(item=str(vector_id), partition_key=str(vector_id))
        except CosmosResourceNotFoundError:
            logger.warning(f"Vector {vector_id} not found in container {self.collection_name}")

    def update(self, vector_id: Union[str, int], vector: Optional[List[float]] = None, payload: Optional[Dict] = None):
        """
        Update a vector and its payload.

        Args:
            vector_id (Union[str, int]): ID of the vector to update.
            vector (list, optional): Updated vector. Defaults to None.
            payload (dict, optional): Updated payload. Defaults to None.
        """
        try:
            item = self.container.read_item(item=str(vector_id), partition_key=str(vector_id))
        except CosmosResourceNotFoundError:
            logger.warning(f"Vector {vector_id} not found in container {self.collection_name}")
            return

        if vector is not None:
            item["vector"] = vector
        if payload is not None:
            item["payload"] = payload

        self.container.upsert_item(item)

    def get(self, vector_id: Union[str, int]) -> Optional[OutputData]:
        """
        Retrieve a vector by ID.

        Args:
            vector_id (Union[str, int]): ID of the vector to retrieve.

        Returns:
            OutputData: Retrieved vector or None if not found.
        """
        try:
            item = self.container.read_item(item=str(vector_id), partition_key=str(vector_id))
        except CosmosResourceNotFoundError:
            return None
        return OutputData(id=item.get("id"), score=None, payload=item.get("payload"))

    def list_cols(self) -> List[str]:
        """
        List all containers in the database.

        Returns:
            list: List of container names.
        """
        return [container["id"] for container in self.database.list_containers()]

    def delete_col(self):
        """Delete the container."""
        try:
            self.database.delete_container(self.collection_name)
            logger.info(f"Container {self.collection_name} deleted successfully")
        except CosmosResourceNotFoundError:
            logger.warning(f"Container {self.collection_name} not found")

    def col_info(self) -> Dict:
        """
        Get information about the container.

        Returns:
            dict: Container properties.
        """
        return self.container.read()

    def list(self, filters: Optional[Dict] = None, top_k: int = 100) -> List[List[OutputData]]:
        """
        List vectors in the container with optional filtering.

        Args:
            filters (dict, optional): Filters to apply to the list. Defaults to None.
            top_k (int, optional): Number of vectors to return. Defaults to 100.

        Returns:
            list: A single-element list containing the list of results.
        """
        where_clause, parameters = self._build_where(filters)
        top_clause = ""
        if top_k is not None:
            top_clause = "TOP @top_k "
            parameters.append({"name": "@top_k", "value": top_k})
        sql = f"SELECT {top_clause}c.id, c.payload FROM c{where_clause}"

        items = self.container.query_items(query=sql, parameters=parameters, enable_cross_partition_query=True)
        results = [OutputData(id=item.get("id"), score=None, payload=item.get("payload")) for item in items]
        return [results]

    def count(self) -> int:
        """
        Count the number of vectors in the container.

        Returns:
            int: Total number of vectors.
        """
        items = list(
            self.container.query_items(query="SELECT VALUE COUNT(1) FROM c", enable_cross_partition_query=True)
        )
        return items[0] if items else 0

    def reset(self):
        """
        Reset the container by deleting and recreating it.
        """
        logger.warning(f"Resetting container {self.collection_name}...")
        self.delete_col()
        self.create_col(self.embedding_model_dims, self.metric)
