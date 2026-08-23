import json
import logging
import os
from typing import Any, Dict, List, Optional, Union

try:
    from polign import Client as PolignClient
    from polign import NotFoundError, PolignError
    from polign import Vector as PolignVector
except ImportError:
    raise ImportError("Polign requires extra dependencies. Install with `pip install polign`") from None

from pydantic import BaseModel

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)

# Polign metadata holds typed scalars (strings, numbers, booleans). The full
# mem0 payload is stored JSON-encoded under this reserved key; scalar payload
# fields are also promoted to plain metadata keys so filters run server-side
# with the right comparison semantics (numbers compare numerically).
PAYLOAD_KEY = "_payload"


class OutputData(BaseModel):
    id: Optional[str]
    score: Optional[float]
    payload: Optional[Dict]


def _is_scalar(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool))


def _scalar(value: Any) -> Any:
    """Metadata form of a scalar, shared by storage and filters.

    Strings, ints, floats, and bools pass through typed so the server
    compares them by type. Anything else falls back to its string form.
    """
    return value if _is_scalar(value) else str(value)


class PolignDB(VectorStoreBase):
    def __init__(
        self,
        collection_name: str,
        embedding_model_dims: int,
        url: str = "http://localhost:23000",
        api_key: Optional[str] = None,
        ef: int = 0,
        batch_size: int = 1000,
    ):
        """
        Initialize the Polign vector store.

        Args:
            collection_name (str): Name of the collection.
            embedding_model_dims (int): Dimensions of the embedding model.
            url (str, optional): Base URL of the polign server's HTTP listener.
                Defaults to "http://localhost:23000".
            api_key (str, optional): API key. Optional — servers started without
                -auth-stores need none. Falls back to POLIGN_API_KEY.
            ef (int, optional): HNSW beam width override (0 = server default).
            batch_size (int, optional): Vectors per put_many request. Defaults to 1000.
        """
        api_key = api_key or os.environ.get("POLIGN_API_KEY")

        self.client = PolignClient(url, api_key=api_key)
        self.collection_name = collection_name
        self.embedding_model_dims = embedding_model_dims
        self.ef = ef
        self.batch_size = min(batch_size, 5000)

    # ── payload <-> metadata ────────────────────────────────────────

    def _encode_payload(self, payload: Optional[Dict]) -> Dict[str, Any]:
        payload = payload or {}
        metadata = {key: value for key, value in payload.items() if _is_scalar(value) and not key.startswith("_")}
        metadata[PAYLOAD_KEY] = json.dumps(payload)
        return metadata

    def _decode_payload(self, metadata: Optional[Dict[str, Any]]) -> Dict:
        metadata = metadata or {}
        raw = metadata.get(PAYLOAD_KEY)
        if raw is not None:
            try:
                return json.loads(raw)
            except (TypeError, ValueError):
                logger.warning("Malformed %s metadata in collection %s", PAYLOAD_KEY, self.collection_name)
        return {k: v for k, v in metadata.items() if k != PAYLOAD_KEY}

    # ── filters ─────────────────────────────────────────────────────

    def _translate_filters(self, filters: Optional[Dict]) -> Optional[Dict]:
        """
        Translate mem0's filter syntax (scalars, lists, eq/ne/gt/gte/lt/lte/
        in/nin operator dicts, AND/OR/NOT) to polign's filter language
        ($eq/$ne/$gt/$gte/$lt/$lte/$in/$exists, $and/$or/$not).
        """
        if not filters:
            return None

        key_map = {"$or": "OR", "$not": "NOT", "$and": "AND"}
        normalized = {}
        for key, value in filters.items():
            norm_key = key_map.get(key, key)
            if norm_key not in normalized:
                normalized[norm_key] = value

        conditions: List[Dict] = []
        for key, value in normalized.items():
            if key in ("AND", "OR", "NOT"):
                if not isinstance(value, list):
                    raise ValueError(f"{key} filter value must be a list of filter dicts, got {type(value).__name__}")
                subs = [s for s in (self._translate_filters(item) for item in value) if s]
                if not subs:
                    continue
                if key == "AND":
                    conditions.append(subs[0] if len(subs) == 1 else {"$and": subs})
                elif key == "OR":
                    conditions.append(subs[0] if len(subs) == 1 else {"$or": subs})
                else:  # NOT
                    conditions.append({"$not": subs[0] if len(subs) == 1 else {"$and": subs}})
            else:
                condition = self._translate_field(key, value)
                if condition is not None:
                    conditions.append(condition)

        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

    def _translate_field(self, key: str, value: Any) -> Optional[Dict]:
        if not isinstance(value, dict):
            if value == "*":
                return {key: {"$exists": True}}
            if isinstance(value, list):
                return {key: {"$in": [_scalar(v) for v in value]}}
            return {key: _scalar(value)}

        ops = {}
        for op, operand in value.items():
            if op in ("eq", "ne", "gt", "gte", "lt", "lte"):
                ops[f"${op}"] = _scalar(operand)
            elif op == "in":
                ops["$in"] = [_scalar(v) for v in operand]
            elif op == "nin":
                return {"$not": {key: {"$in": [_scalar(v) for v in operand]}}}
            else:
                raise ValueError(f"Unsupported filter operator '{op}' for field '{key}' in Polign")
        return {key: ops} if ops else None

    # ── VectorStoreBase ─────────────────────────────────────────────

    def create_col(self, name=None, vector_size=None, distance=None):
        """
        Create a new collection.
        Collections are auto-created on first put, so this is a no-op.
        """
        pass

    def insert(
        self,
        vectors: List[List[float]],
        payloads: Optional[List[Dict]] = None,
        ids: Optional[List[Union[str, int]]] = None,
    ):
        """
        Insert vectors into the collection.

        Args:
            vectors (list): List of vectors to insert.
            payloads (list, optional): List of payloads corresponding to vectors.
            ids (list, optional): List of IDs corresponding to vectors.
        """
        logger.info(f"Inserting {len(vectors)} vectors into collection {self.collection_name}")

        if ids is None:
            ids = [str(i) for i in range(len(vectors))]

        rows = [
            PolignVector(
                id=str(ids[i]),
                values=vectors[i],
                metadata=self._encode_payload(payloads[i] if payloads else None),
            )
            for i in range(len(vectors))
        ]
        for i in range(0, len(rows), self.batch_size):
            self.client.put_many(self.collection_name, rows[i : i + self.batch_size])

    def search(
        self, query: str, vectors: List[float], top_k: int = 5, filters: Optional[Dict] = None
    ) -> List[OutputData]:
        """
        Search for similar vectors.

        Args:
            query (str): Query text (unused in vector search, kept for interface consistency).
            vectors (list): Query vector to search with.
            top_k (int, optional): Number of results to return. Defaults to 5.
            filters (dict, optional): Filters to apply to the search.

        Returns:
            list: Search results.
        """
        try:
            hits = self.client.search(
                self.collection_name,
                values=vectors,
                k=top_k,
                ef=self.ef,
                filter=self._translate_filters(filters),
            )
        except NotFoundError:
            return []
        # Auto-created collections use the L2 metric: similarity = 1 / (1 + distance).
        return [
            OutputData(
                id=hit.id,
                score=1.0 / (1.0 + hit.distance),
                payload=self._decode_payload(hit.metadata),
            )
            for hit in hits
        ]

    def keyword_search(self, query: str, top_k: int = 5, filters: Optional[Dict] = None) -> Optional[List[OutputData]]:
        """
        BM25 full-text search (requires a segment index server-side).

        Returns None if the server cannot serve a text search.
        """
        try:
            hits = self.client.search(
                self.collection_name,
                text=query,
                k=top_k,
                filter=self._translate_filters(filters),
            )
        except PolignError as e:
            logger.debug(f"Polign keyword search unavailable: {e}")
            return None
        return [OutputData(id=hit.id, score=hit.score, payload=self._decode_payload(hit.metadata)) for hit in hits]

    def delete(self, vector_id: Union[str, int]):
        """
        Delete a vector by ID.

        Args:
            vector_id (Union[str, int]): ID of the vector to delete.
        """
        self.client.delete(self.collection_name, str(vector_id))

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
            vector (list, optional): Updated vector.
            payload (dict, optional): Updated payload.
        """
        existing = self.client.get(self.collection_name, str(vector_id))
        self.client.put(
            self.collection_name,
            str(vector_id),
            vector if vector is not None else existing.values,
            metadata=self._encode_payload(payload) if payload is not None else existing.metadata,
        )

    def get(self, vector_id: Union[str, int]) -> Optional[OutputData]:
        """
        Retrieve a vector by ID.

        Args:
            vector_id (Union[str, int]): ID of the vector to retrieve.

        Returns:
            OutputData: Retrieved vector data, or None if not found.
        """
        try:
            vector = self.client.get(self.collection_name, str(vector_id))
        except NotFoundError:
            return None
        return OutputData(id=vector.id, score=None, payload=self._decode_payload(vector.metadata))

    def list_cols(self) -> List[str]:
        """
        List all collections.

        Returns:
            list: List of collection names.
        """
        try:
            return [c.name for c in self.client.list_collections()]
        except PolignError as e:
            logger.debug(f"Error listing collections: {e}")
            return []

    def delete_col(self):
        """Delete the collection (falls back to deleting every vector)."""
        try:
            self.client.delete_collection(self.collection_name)
            return
        except PolignError as e:
            logger.debug(f"delete_collection unavailable, deleting vectors instead: {e}")
        try:
            while True:
                page = self.client.list(self.collection_name, limit=self.batch_size)
                if not page.vectors:
                    break
                for vector in page.vectors:
                    self.client.delete(self.collection_name, vector.id)
        except NotFoundError:
            pass

    def col_info(self) -> Dict:
        """
        Get information about the collection.

        Returns:
            dict: Collection name and vector count.
        """
        try:
            page = self.client.list(self.collection_name, limit=1)
            return {"name": self.collection_name, "count": page.total}
        except PolignError:
            return {"name": self.collection_name}

    def list(self, filters: Optional[Dict] = None, top_k: Optional[int] = 100) -> List[List[OutputData]]:
        """
        List vectors with optional filtering.

        Filters run server-side (polign's list takes the same filter language
        as search); offset and the page total count matching vectors only, so
        pagination works unchanged under a filter.

        Args:
            filters (dict, optional): Filters to apply.
            top_k (int, optional): Number of vectors to return. Defaults to 100.

        Returns:
            list: Wrapped list of OutputData objects ([[results]]).
        """
        translated = self._translate_filters(filters)
        results: List[OutputData] = []
        offset = 0
        try:
            while top_k is None or len(results) < top_k:
                limit = self.batch_size if top_k is None else min(self.batch_size, top_k - len(results))
                page = self.client.list(self.collection_name, limit=limit, offset=offset, filter=translated)
                if not page.vectors:
                    break
                for vector in page.vectors:
                    results.append(OutputData(id=vector.id, score=None, payload=self._decode_payload(vector.metadata)))
                    if top_k is not None and len(results) >= top_k:
                        break
                offset += len(page.vectors)
                if offset >= page.total:
                    break
        except NotFoundError:
            pass
        return [results]

    def count(self) -> int:
        """
        Get the live vector count of the collection.

        Returns:
            int: Number of vectors.
        """
        try:
            return self.client.list(self.collection_name, limit=1).total
        except PolignError:
            return 0

    def reset(self):
        """Reset the collection by deleting all vectors (recreated on next insert)."""
        self.delete_col()
