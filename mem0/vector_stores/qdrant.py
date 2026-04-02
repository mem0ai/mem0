import logging
import re
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    DatetimeRange,
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    MatchExcept,
    MatchText,
    MatchValue,
    PointIdsList,
    PointStruct,
    PointVectors,
    Range,
    VectorParams,
)

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)


class Qdrant(VectorStoreBase):
    def __init__(
        self,
        collection_name: str,
        embedding_model_dims: int,
        client: QdrantClient = None,
        host: str = None,
        port: int = None,
        path: str = None,
        url: str = None,
        api_key: str = None,
        on_disk: bool = False,
    ):
        """
        Initialize the Qdrant vector store.

        Args:
            collection_name (str): Name of the collection.
            embedding_model_dims (int): Dimensions of the embedding model.
            client (QdrantClient, optional): Existing Qdrant client instance. Defaults to None.
            host (str, optional): Host address for Qdrant server. Defaults to None.
            port (int, optional): Port for Qdrant server. Defaults to None.
            path (str, optional): Path for local Qdrant database. Defaults to None.
            url (str, optional): Full URL for Qdrant server. Defaults to None.
            api_key (str, optional): API key for Qdrant server. Defaults to None.
            on_disk (bool, optional): Enables persistent storage. Vectors are stored on disk (True) or in memory (False).
                Does not delete the local database path. Defaults to False.
        """
        if client:
            self.client = client
            self.is_local = False
        else:
            params = {}
            if api_key:
                params["api_key"] = api_key
            if url:
                params["url"] = url
            if host and port:
                params["host"] = host
                params["port"] = port
            
            if not params:
                params["path"] = path
                self.is_local = True
            else:
                self.is_local = False

            self.client = QdrantClient(**params)

        self.collection_name = collection_name
        self.embedding_model_dims = embedding_model_dims
        self.on_disk = on_disk
        self.create_col(embedding_model_dims, on_disk)

    def create_col(self, vector_size: int, on_disk: bool, distance: Distance = Distance.COSINE):
        """
        Create a new collection.

        Args:
            vector_size (int): Size of the vectors to be stored.
            on_disk (bool): Enables persistent storage.
            distance (Distance, optional): Distance metric for vector similarity. Defaults to Distance.COSINE.
        """
        # Skip creating collection if already exists
        response = self.list_cols()
        for collection in response.collections:
            if collection.name == self.collection_name:
                logger.debug(f"Collection {self.collection_name} already exists. Skipping creation.")
                self._create_filter_indexes()
                return

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=vector_size, distance=distance, on_disk=on_disk),
        )
        self._create_filter_indexes()

    def _create_filter_indexes(self):
        """Create indexes for commonly used filter fields to enable filtering."""
        # Only create payload indexes for remote Qdrant servers
        if self.is_local:
            logger.debug("Skipping payload index creation for local Qdrant (not supported)")
            return
            
        common_fields = ["user_id", "agent_id", "run_id", "actor_id"]
        
        for field in common_fields:
            try:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field,
                    field_schema="keyword"
                )
                logger.info(f"Created index for {field} in collection {self.collection_name}")
            except Exception as e:
                logger.debug(f"Index for {field} might already exist: {e}")

    def insert(self, vectors: list, payloads: list = None, ids: list = None):
        """
        Insert vectors into a collection.

        Args:
            vectors (list): List of vectors to insert.
            payloads (list, optional): List of payloads corresponding to vectors. Defaults to None.
            ids (list, optional): List of IDs corresponding to vectors. Defaults to None.
        """
        logger.info(f"Inserting {len(vectors)} vectors into collection {self.collection_name}")
        points = [
            PointStruct(
                id=idx if ids is None else ids[idx],
                vector=vector,
                payload=payloads[idx] if payloads else {},
            )
            for idx, vector in enumerate(vectors)
        ]
        self.client.upsert(collection_name=self.collection_name, points=points)

    # ISO 8601 datetime pattern for detecting datetime strings in range filters
    _ISO_DATETIME_RE = re.compile(
        r"^\d{4}-\d{2}-\d{2}"  # date part
        r"([T ]\d{2}:\d{2}(:\d{2})?"  # optional time part
        r"(\.\d+)?"  # optional fractional seconds
        r"(Z|[+-]\d{2}:?\d{2})?"  # optional timezone
        r")?$"
    )

    @staticmethod
    def _is_datetime_range(range_kwargs: dict) -> bool:
        """Check if all values in range kwargs are ISO datetime strings."""
        return all(
            isinstance(v, str) and Qdrant._ISO_DATETIME_RE.match(v)
            for v in range_kwargs.values()
        )

    def _build_field_condition(self, key: str, value) -> Optional[FieldCondition]:
        """
        Build a single FieldCondition from a key-value filter pair.

        Supports the enhanced filter syntax documented at
        https://docs.mem0.ai/open-source/features/metadata-filtering

        Args:
            key (str): The payload field name.
            value: A scalar for simple equality, or a dict with one operator key.

        Returns:
            Optional[FieldCondition]: The Qdrant field condition, or None if the
            value is the wildcard '*' (match any / field exists — skip filter).
        """
        if not isinstance(value, dict):
            if value == "*":
                # Wildcard: match any value. Qdrant has no direct "field exists"
                # condition via FieldCondition, so we skip this filter (match all).
                return None
            if isinstance(value, list):
                # List shorthand: {"field": ["a", "b"]} treated as in-operator.
                return FieldCondition(key=key, match=MatchAny(any=value))
            # Simple equality: {"field": "value"}
            return FieldCondition(key=key, match=MatchValue(value=value))

        ops = set(value.keys())
        range_ops = {"gt", "gte", "lt", "lte"}
        non_range_ops = ops - range_ops

        if ops & range_ops:
            if non_range_ops:
                raise ValueError(
                    f"Cannot mix range operators ({ops & range_ops}) with "
                    f"non-range operators ({non_range_ops}) for field '{key}'. "
                    f"Use AND to combine them as separate conditions."
                )
            range_kwargs = {op: value[op] for op in range_ops if op in value}
            if self._is_datetime_range(range_kwargs):
                try:
                    return FieldCondition(key=key, range=DatetimeRange(**range_kwargs))
                except (ValueError, TypeError) as e:
                    raise ValueError(
                        f"Invalid datetime value in range filter for field '{key}': {e}"
                    ) from e
            return FieldCondition(key=key, range=Range(**range_kwargs))
        elif "eq" in value:
            return FieldCondition(key=key, match=MatchValue(value=value["eq"]))
        elif "ne" in value:
            return FieldCondition(key=key, match=MatchExcept(**{"except": [value["ne"]]}))
        elif "in" in value:
            return FieldCondition(key=key, match=MatchAny(any=value["in"]))
        elif "nin" in value:
            return FieldCondition(key=key, match=MatchExcept(**{"except": value["nin"]}))
        elif "contains" in value or "icontains" in value:
            # MatchText: with a full-text index, tokenized matching (all words must appear).
            # Without a full-text index, exact substring match.
            op = "icontains" if "icontains" in value else "contains"
            text = value[op]
            if op == "icontains":
                logger.debug(
                    "icontains on field '%s': Qdrant MatchText case sensitivity depends on "
                    "full-text index configuration. Without a full-text index this behaves "
                    "as a case-sensitive substring match (same as 'contains').",
                    key,
                )
            return FieldCondition(key=key, match=MatchText(text=text))
        else:
            supported = {"eq", "ne", "gt", "gte", "lt", "lte", "in", "nin", "contains", "icontains"}
            raise ValueError(
                f"Unsupported filter operator(s) for field '{key}': {ops}. "
                f"Supported operators: {supported}"
            )

    def _create_filter(self, filters: dict) -> Optional[Filter]:
        """
        Create a Filter object from the provided filters.

        Supports the enhanced filter syntax with comparison operators (eq, ne,
        gt, gte, lt, lte), list operators (in, nin), string operators (contains,
        icontains), and logical operators (AND, OR, NOT).

        Args:
            filters (dict): Filters to apply.

        Returns:
            Filter: The created Filter object, or None if filters is empty.
        """
        if not filters:
            return None

        # Normalize $or/$not/$and → OR/NOT/AND and deduplicate.
        # Memory._process_metadata_filters() renames OR→$or and NOT→$not,
        # but effective_filters retains the original OR/NOT keys from
        # deepcopy(input_filters).  Without dedup the same sub-conditions
        # would be evaluated twice.
        key_map = {"$or": "OR", "$not": "NOT", "$and": "AND"}
        normalized = {}
        for key, value in filters.items():
            norm_key = key_map.get(key, key)
            if norm_key not in normalized:
                normalized[norm_key] = value

        must = []
        should = []
        must_not = []

        for key, value in normalized.items():
            if key in ("AND", "OR", "NOT"):
                if not isinstance(value, list):
                    raise ValueError(
                        f"{key} filter value must be a list of filter dicts, "
                        f"got {type(value).__name__}"
                    )
                for i, item in enumerate(value):
                    if not isinstance(item, dict):
                        raise ValueError(
                            f"{key} filter list item at index {i} must be a dict, "
                            f"got {type(item).__name__}: {item!r}"
                        )

            if key == "AND":
                for sub in value:
                    built = self._create_filter(sub)
                    if built:
                        must.append(built)
            elif key == "OR":
                for sub in value:
                    built = self._create_filter(sub)
                    if built:
                        should.append(built)
            elif key == "NOT":
                for sub in value:
                    built = self._create_filter(sub)
                    if built:
                        must_not.append(built)
            else:
                condition = self._build_field_condition(key, value)
                if condition is not None:
                    must.append(condition)

        if not any([must, should, must_not]):
            return None

        return Filter(
            must=must or None,
            should=should or None,
            must_not=must_not or None,
        )

    def search(self, query: str, vectors: list, limit: int = 5, filters: dict = None) -> list:
        """
        Search for similar vectors.

        Args:
            query (str): Query.
            vectors (list): Query vector.
            limit (int, optional): Number of results to return. Defaults to 5.
            filters (dict, optional): Filters to apply to the search. Defaults to None.

        Returns:
            list: Search results.
        """
        query_filter = self._create_filter(filters) if filters else None
        hits = self.client.query_points(
            collection_name=self.collection_name,
            query=vectors,
            query_filter=query_filter,
            limit=limit,
        )
        return hits.points

    def delete(self, vector_id: int):
        """
        Delete a vector by ID.

        Args:
            vector_id (int): ID of the vector to delete.
        """
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=PointIdsList(
                points=[vector_id],
            ),
        )

    def update(self, vector_id: int, vector: list = None, payload: dict = None):
        """
        Update a vector and its payload.

        Args:
            vector_id (int): ID of the vector to update.
            vector (list, optional): Updated vector. Defaults to None.
            payload (dict, optional): Updated payload. Defaults to None.
        """
        if vector is not None and payload is not None:
            point = PointStruct(id=vector_id, vector=vector, payload=payload)
            self.client.upsert(collection_name=self.collection_name, points=[point])
        else:
            if payload is not None:
                self.client.set_payload(
                    collection_name=self.collection_name,
                    payload=payload,
                    points=[vector_id],
                )
            if vector is not None:
                self.client.update_vectors(
                    collection_name=self.collection_name,
                    points=[PointVectors(id=vector_id, vector=vector)],
                )

    def get(self, vector_id: int) -> dict:
        """
        Retrieve a vector by ID.

        Args:
            vector_id (int): ID of the vector to retrieve.

        Returns:
            dict: Retrieved vector.
        """
        result = self.client.retrieve(collection_name=self.collection_name, ids=[vector_id], with_payload=True)
        return result[0] if result else None

    def list_cols(self) -> list:
        """
        List all collections.

        Returns:
            list: List of collection names.
        """
        return self.client.get_collections()

    def delete_col(self):
        """Delete a collection."""
        self.client.delete_collection(collection_name=self.collection_name)

    def col_info(self) -> dict:
        """
        Get information about a collection.

        Returns:
            dict: Collection information.
        """
        return self.client.get_collection(collection_name=self.collection_name)

    def list(self, filters: dict = None, limit: int = 100) -> list:
        """
        List all vectors in a collection.

        Args:
            filters (dict, optional): Filters to apply to the list. Defaults to None.
            limit (int, optional): Number of vectors to return. Defaults to 100.

        Returns:
            list: List of vectors.
        """
        query_filter = self._create_filter(filters) if filters else None
        result = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=query_filter,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        return result

    def reset(self):
        """Reset the index by deleting and recreating it."""
        logger.warning(f"Resetting index {self.collection_name}...")
        self.delete_col()
        self.create_col(self.embedding_model_dims, self.on_disk)
