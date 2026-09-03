import logging
import re
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

_SAFE_FILTER_KEY = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_.]*$")
_IDENTITY_FILTER_KEYS = ("user_id", "agent_id", "run_id")


def _validate_filter_key(key: str) -> None:
    """Validate that a filter key is safe (no injection)."""
    if not isinstance(key, str) or not _SAFE_FILTER_KEY.match(key):
        raise ValueError(f"Invalid filter key: {key!r}")


def _validate_scalar(value) -> None:
    """Validate that a scalar filter value is safe."""
    if not isinstance(value, (str, int, float, bool)):
        raise ValueError(
            f"Filter value must be str, int, float, or bool, got {type(value).__name__}"
        )


def _build_field_clause(key: str, value) -> Optional[dict]:
    """Build a single OpenSearch filter clause from a key-value pair.

    Supports the enhanced filter syntax documented at
    https://docs.mem0.ai/open-source/features/metadata-filtering

    Args:
        key: The payload field name.
        value: A scalar for simple equality, a dict with operator keys,
               or "*" for exists wildcard.

    Returns:
        An OpenSearch DSL filter clause dict, or None for "*" wildcard
        (field exists — handled separately).
    """
    if value == "*":
        # "Any value" wildcard: match documents where the field exists.
        _validate_filter_key(key)
        return {"exists": {"field": f"payload.{key}"}}

    if not isinstance(value, dict):
        # Simple equality: {"field": "value"}
        # List shorthand: {"field": ["a", "b"]} treated as in-operator.
        if isinstance(value, list):
            for item in value:
                _validate_scalar(item)
            _validate_filter_key(key)
            first_scalar = value[0] if value else None
            field = f"payload.{key}.keyword" if isinstance(first_scalar, str) else f"payload.{key}"
            return {"terms": {field: value}}
        _validate_scalar(value)
        _validate_filter_key(key)
        field = f"payload.{key}.keyword" if isinstance(value, str) else f"payload.{key}"
        return {"term": {field: value}}

    # Operator dict: {"priority": {"gte": 3}}
    _validate_filter_key(key)

    ops = set(value.keys())
    range_ops = {"gt", "gte", "lt", "lte"}
    non_range_ops = ops - range_ops

    # Build range clause
    if ops & range_ops:
        if non_range_ops:
            raise ValueError(
                f"Cannot mix range operators ({ops & range_ops}) with "
                f"non-range operators ({non_range_ops}) for field '{key}'. "
                f"Use AND to combine them as separate conditions."
            )
        range_kwargs = {op: value[op] for op in range_ops if op in value}
        return {"range": {f"payload.{key}": range_kwargs}}

    # Single-operator clauses (one key only in the value dict)
    if "eq" in value:
        v = value["eq"]
        _validate_scalar(v)
        field = f"payload.{key}.keyword" if isinstance(v, str) else f"payload.{key}"
        return {"term": {field: v}}

    if "ne" in value:
        v = value["ne"]
        _validate_scalar(v)
        field = f"payload.{key}.keyword" if isinstance(v, str) else f"payload.{key}"
        return {"bool": {"must_not": {"term": {field: v}}}}

    if "in" in value:
        v = value["in"]
        if not isinstance(v, list):
            raise ValueError(f"'in' operator value must be a list, got {type(v).__name__}")
        for item in v:
            _validate_scalar(item)
        # Use terms query for all values; .keyword subfield for strings.
        first_scalar = v[0] if v else None
        field = f"payload.{key}.keyword" if isinstance(first_scalar, str) else f"payload.{key}"
        return {"terms": {field: v}}

    if "nin" in value:
        v = value["nin"]
        if not isinstance(v, list):
            raise ValueError(f"'nin' operator value must be a list, got {type(v).__name__}")
        for item in v:
            _validate_scalar(item)
        first_scalar = v[0] if v else None
        field = f"payload.{key}.keyword" if isinstance(first_scalar, str) else f"payload.{key}"
        return {"bool": {"must_not": {"terms": {field: v}}}}

    if "contains" in value:
        text = value["contains"]
        if not isinstance(text, str):
            raise ValueError(f"'contains' operator value must be a string, got {type(text).__name__}")
        return {"wildcard": {f"payload.{key}.keyword": f"*{text}*"}}

    if "icontains" in value:
        text = value["icontains"]
        if not isinstance(text, str):
            raise ValueError(f"'icontains' operator value must be a string, got {type(text).__name__}")
        return {
            "wildcard": {
                f"payload.{key}.keyword": {
                    "value": f"*{text}*",
                    "case_insensitive": True,
                }
            }
        }

    supported = {"eq", "ne", "gt", "gte", "lt", "lte", "in", "nin", "contains", "icontains"}
    raise ValueError(
        f"Unsupported filter operator(s) for field '{key}': {ops}. "
        f"Supported operators: {supported}"
    )


def _build_filter_clauses(filters: Optional[Dict[str, Any]]) -> List[dict]:
    """Build OpenSearch DSL filter clauses from the documented filter grammar.

    Supports comparison operators (eq, ne, gt, gte, lt, lte),
    list operators (in, nin), string operators (contains, icontains),
    logical operators ($or, $not), and the wildcard "*" (exists).
    """
    if not filters:
        return []

    # Normalize $or/$not/$and → OR/NOT/AND and deduplicate.
    key_map = {"$or": "OR", "$not": "NOT", "$and": "AND"}
    normalized = {}
    for key, value in filters.items():
        norm_key = key_map.get(key, key)
        if norm_key not in normalized:
            normalized[norm_key] = value

    filter_clauses = []

    for key, value in normalized.items():
        if value is None:
            continue
        if key in ("AND", "OR", "NOT"):
            if not isinstance(value, list):
                raise ValueError(
                    f"{key} filter value must be a list of filter dicts, "
                    f"got {type(value).__name__}"
                )
            sub_clauses = []
            for item in value:
                if not isinstance(item, dict):
                    raise ValueError(
                        f"{key} filter list item must be a dict, "
                        f"got {type(item).__name__}: {item!r}"
                    )
                # Recursively build clauses for each sub-filter
                sub = _build_filter_clauses(item)
                if sub:
                    sub_clauses.extend(sub)
            if not sub_clauses:
                continue
            if key == "OR":
                filter_clauses.append({"bool": {"should": sub_clauses, "minimum_should_match": 1}})
            elif key == "NOT":
                filter_clauses.append({"bool": {"must_not": sub_clauses}})
            else:  # AND
                filter_clauses.extend(sub_clauses)
        else:
            clause = _build_field_clause(key, value)
            if clause is not None:
                filter_clauses.append(clause)

    return filter_clauses


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
        self.auto_refresh = config.auto_refresh

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
                    "metadata": {
                        "type": "object",
                        "properties": {
                            "user_id": {"type": "keyword"},
                            "agent_id": {"type": "keyword"},
                            "run_id": {"type": "keyword"},
                        },
                    },
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

        for idx, vec in enumerate(vectors):
            if vec is None:
                raise ValueError(
                    f"Vector at index {idx} is null. "
                    f"This usually means the embedding model failed to generate an embedding. "
                    f"Check that your embedding model is configured correctly and returning valid vectors."
                )
            if len(vec) == 0:
                raise ValueError(
                    f"Vector at index {idx} is empty. "
                    f"Expected a vector of dimension {self.embedding_model_dims}, got an empty vector."
                )
            if len(vec) != self.embedding_model_dims:
                raise ValueError(
                    f"Vector at index {idx} has dimension {len(vec)}, "
                    f"but the index '{self.collection_name}' expects dimension {self.embedding_model_dims}. "
                    f"Ensure your embedding model's output dimensions match the vector store configuration."
                )

        results = []
        for i, (vec, id_) in enumerate(zip(vectors, ids)):
            body = {
                "vector_field": vec,
                "payload": payloads[i],
                "id": id_,
            }
            try:
                self.client.index(index=self.collection_name, body=body)

                results.append(
                    OutputData(
                        id=id_,
                        score=1.0,  # No score for inserts
                        payload=payloads[i],
                    )
                )
            except Exception as e:
                logger.error(f"Error inserting vector {id_}: {e}", exc_info=True)
                raise

        # Refresh once after the full batch (not per document) if explicitly enabled.
        # Disabled by default for Serverless compatibility: OpenSearch Serverless does not
        # support the indices.refresh() API, and refreshing per document would cause a
        # cluster-level I/O stall on every insert.
        # See: https://docs.aws.amazon.com/opensearch-service/latest/developerguide/serverless-genref.html
        if self.auto_refresh:
            self.client.indices.refresh(index=self.collection_name)

        return results

    def search(
        self, query: str, vectors: List[float], top_k: int = 5, filters: Optional[Dict] = None
    ) -> List[OutputData]:
        """Search for similar vectors using OpenSearch k-NN search with optional filters."""

        # Base KNN query
        knn_query = {
            "knn": {
                "vector_field": {
                    "vector": vectors,
                    "k": top_k * 2,
                }
            }
        }

        # Start building the full query
        query_body = {"size": top_k * 2, "query": None}

        # Prepare filter conditions if applicable
        filter_clauses = _build_filter_clauses(filters)

        # Combine knn with filters if needed
        if filter_clauses:
            query_body["query"] = {"bool": {"must": knn_query, "filter": filter_clauses}}
        else:
            query_body["query"] = knn_query

        try:
            # Execute search
            response = self.client.search(index=self.collection_name, body=query_body)

            hits = response["hits"]["hits"]
            results = [
                OutputData(id=hit["_source"].get("id"), score=hit["_score"], payload=hit["_source"].get("payload", {}))
                for hit in hits[:top_k]  # Ensure we don't exceed top_k
            ]
            return results
        except Exception as e:
            logger.error(f"Error during search: {e}", exc_info=True)
            raise

    def keyword_search(self, query, top_k=5, filters=None):
        """Search for memories using BM25 keyword matching.

        Args:
            query (str): The text query to search for.
            top_k (int): Maximum number of results to return. Defaults to 5.
            filters (Dict, optional): Filters to apply to the search.

        Returns:
            List[OutputData]: Search results with id, score, and payload.
        """
        # Build a multi_match query across text fields in payload
        should_clauses = [
            {"match": {"payload.data": query}},
            {"match": {"payload.text_lemmatized": query}},
        ]

        bool_query = {
            "should": should_clauses,
            "minimum_should_match": 1,
        }

        # Apply filters consistently with the existing search() method
        filter_clauses = _build_filter_clauses(filters)

        if filter_clauses:
            bool_query["filter"] = filter_clauses

        query_body = {
            "size": top_k,
            "query": {"bool": bool_query},
        }

        try:
            response = self.client.search(index=self.collection_name, body=query_body)

            hits = response["hits"]["hits"]
            results = [
                OutputData(id=hit["_source"].get("id"), score=hit["_score"], payload=hit["_source"].get("payload", {}))
                for hit in hits[:top_k]
            ]
            return results
        except Exception as e:
            # Do NOT re-raise here: keyword_search() is a best-effort helper that
            # search() may call to augment semantic results. Raising would crash
            # the whole search() call on a keyword-only failure (regression per
            # maintainer review on #6519). Log with exc_info and degrade to None.
            logger.error(f"Error during keyword search: {e}", exc_info=True)
            return None

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
        if vector is not None:
            if len(vector) == 0:
                raise ValueError("Cannot update with an empty vector.")
            if len(vector) != self.embedding_model_dims:
                raise ValueError(
                    f"Update vector has dimension {len(vector)}, "
                    f"but the index '{self.collection_name}' expects dimension {self.embedding_model_dims}. "
                    f"Ensure your embedding model's output dimensions match the vector store configuration."
                )

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
            except Exception as e:
                logger.error(f"Error updating vector {vector_id}: {e}", exc_info=True)
                raise

    def get(self, vector_id: str) -> Optional[OutputData]:
        """Retrieve a vector by ID."""
        try:
            search_query = {"query": {"term": {"id": vector_id}}}
            response = self.client.search(index=self.collection_name, body=search_query)

            hits = response["hits"]["hits"]

            if not hits:
                return None

            return OutputData(id=hits[0]["_source"].get("id"), score=1.0, payload=hits[0]["_source"].get("payload", {}))
        except Exception as e:
            logger.error(f"Error retrieving vector {vector_id}: {str(e)}", exc_info=True)
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

    def list(self, filters: Optional[Dict] = None, top_k: Optional[int] = None) -> List[OutputData]:
        try:
            """List all memories with optional filters."""
            query: Dict = {"query": {"match_all": {}}}

            filter_clauses = _build_filter_clauses(filters)

            if filter_clauses:
                query["query"] = {"bool": {"filter": filter_clauses}}

            if top_k:
                query["size"] = top_k

            response = self.client.search(index=self.collection_name, body=query)
            hits = response["hits"]["hits"]

            # Return a flat list, not a nested array
            results = [
                OutputData(id=hit["_source"].get("id"), score=1.0, payload=hit["_source"].get("payload", {}))
                for hit in hits
            ]
            return [results]  # VectorStore expects tuple/list format
        except Exception as e:
            logger.error(f"Error listing vectors: {e}", exc_info=True)
            return [[]]

    def reset(self):
        """Reset the index by deleting and recreating it."""
        logger.warning(f"Resetting index {self.collection_name}...")
        self.delete_col()
        self.create_col(self.collection_name, self.embedding_model_dims)
