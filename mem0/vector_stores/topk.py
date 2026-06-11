import logging
import os
import secrets
from typing import Any, Dict, List, Literal, Optional, Union, cast

try:
    from topk_sdk import Client
    from topk_sdk.error import (
        CollectionAlreadyExistsError,
        CollectionNotFoundError,
        InvalidArgumentError,
    )
    from topk_sdk.query import LogicalExpr
    from topk_sdk.query import all as topk_all
    from topk_sdk.query import field
    from topk_sdk.query import filter as topk_filter
    from topk_sdk.query import fn, match, not_, select
    from topk_sdk.schema import f32_vector, keyword_index, text, vector_index
except ImportError:
    raise ImportError("Could not import TopK SDK. Install with `pip install topk-sdk`") from None

from pydantic import BaseModel

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)

_METRIC_MAP = {"cosine": "cosine", "euclidean": "euclidean", "dot": "dot_product"}
_MIGRATIONS_COLLECTION_NAME = "memory_migrations"
_USER_ID_RECORD_ID = "user_id_record"

# All fields Mem0 expects in the payload
# See: mem0/memory/main.py (core_and_promoted_keys)
_MEM0_FIELDS = (
    "data",
    "hash",
    "created_at",
    "updated_at",
    "text_lemmatized",
    "attributed_to",
    "user_id",
    "agent_id",
    "run_id",
    "actor_id",
    "role",
)


class OutputData(BaseModel):
    id: Optional[str] = None
    score: Optional[float] = None
    payload: Optional[Dict] = None


class TopK(VectorStoreBase):
    """TopK vector store integration for Mem0.

    TopK is a managed, high-performance vector database built for large-scale
    semantic memory workloads. This adapter supports dense vector search,
    native BM25 keyword search over lemmatized memory text, schemaless metadata
    filtering, and optional partition-scoped operations for multi-tenant
    applications.
    """

    def __init__(
        self,
        collection_name: str,
        embedding_model_dims: int,
        api_key: Optional[str] = None,
        region: Optional[str] = None,
        host: Optional[str] = None,
        https: Optional[bool] = None,
        distance_metric: str = "cosine",
        batch_size: int = 100,
        partition: Optional[str] = None,
    ):
        api_key = api_key or os.environ.get("TOPK_API_KEY")
        if not api_key:
            raise ValueError("TopK API key must be provided as a parameter or via TOPK_API_KEY environment variable")
        region = region or os.environ.get("TOPK_REGION")
        if not region:
            raise ValueError("TopK region must be provided as a parameter or via TOPK_REGION environment variable")
        host = host or os.environ.get("TOPK_HOST")
        if https is None:
            env_https = os.environ.get("TOPK_HTTPS")
            https = env_https.lower() not in ("0", "false", "no") if env_https is not None else True

        client_kwargs: Dict[str, Any] = {"api_key": api_key, "region": region, "https": https}
        if host:
            client_kwargs["host"] = host
        self.client = Client(**client_kwargs)
        self.collection_name = collection_name
        self.embedding_model_dims = embedding_model_dims
        self.distance_metric = distance_metric
        self.batch_size = batch_size
        self.partition = partition
        self._last_write_lsn: Optional[str] = None
        self._cached_user_id: Optional[str] = None
        self.create_col(collection_name, embedding_model_dims, distance_metric)

    def _col(self):
        return self.client.collection(self.collection_name, self.partition)

    def _topk_metric(self) -> str:
        return _METRIC_MAP.get(self.distance_metric, "cosine")

    def _to_similarity(self, raw: float) -> float:
        """Normalize fn.vector_distance output to similarity (higher = better).

        TopK's fn.vector_distance returns:
          cosine     → cosine similarity  (1 = identical, already higher = better)
          euclidean  → euclidean distance (0 = identical, needs inversion)
          dot_product → dot product       (already higher = better)
        """
        if self._topk_metric() == "euclidean":
            return 1.0 / (1.0 + raw)
        return raw  # cosine or dot_product: already higher = better

    def _search_asc(self) -> bool:
        """Whether topk should sort ascending (True for euclidean distance, False for similarity)."""
        return self._topk_metric() == "euclidean"

    def _convert_filters(self, filters: Dict) -> List[LogicalExpr]:
        conditions = []
        for key, value in filters.items():
            if isinstance(value, dict):
                for op, val in value.items():
                    if op == "eq":
                        conditions.append(field(key) == val)
                    elif op == "ne":
                        conditions.append(field(key).ne(val))
                    elif op == "gt":
                        conditions.append(field(key) > val)
                    elif op == "gte":
                        conditions.append(field(key) >= val)
                    elif op == "lt":
                        conditions.append(field(key) < val)
                    elif op == "lte":
                        conditions.append(field(key) <= val)
                    elif op == "in":
                        conditions.append(field(key).in_(val))
                    elif op == "nin":
                        conditions.append(not_(field(key).in_(val)))
                    elif op == "contains":
                        conditions.append(field(key).contains(val))
                    else:
                        raise ValueError(f"Unsupported filter operator: '{op}'")
            else:
                conditions.append(field(key) == value)
        return topk_all(conditions)

    @staticmethod
    def _payload_from(doc: Dict) -> Dict:
        return {k: v for k, v in doc.items() if k not in ("_id", "vector", "score")}

    @staticmethod
    def _select_fields(filters: Optional[Dict]) -> List[str]:
        """Fields to request from a query.

        TopK's select() has no wildcard, so we whitelist Mem0's payload fields
        plus any filter keys — custom metadata is returned only when it is also
        used as a filter key.
        """
        extra = [k for k in (filters or {}) if k not in _MEM0_FIELDS and k not in ("score", "vector", "_id")]
        return [*_MEM0_FIELDS, *extra]

    def create_col(self, name: str, vector_size: int, distance: str):
        try:
            self.client.collections().create(
                name,
                schema={
                    "vector": f32_vector(vector_size).index(
                        vector_index(
                            metric=cast(
                                Literal["cosine", "euclidean", "dot_product", "hamming"],
                                _METRIC_MAP.get(distance, "cosine"),
                            )
                        )
                    ),
                    "text_lemmatized": text().index(keyword_index()),
                },
            )
        except CollectionAlreadyExistsError:
            pass

    def insert(
        self,
        vectors: List[List[float]],
        payloads: Optional[List[Dict]] = None,
        ids: Optional[List] = None,
    ):
        if ids is None:
            ids = [str(i) for i in range(len(vectors))]
        for i in range(0, len(vectors), self.batch_size):
            batch = []
            for j in range(i, min(i + self.batch_size, len(vectors))):
                doc: Dict[str, Any] = {"_id": str(ids[j]), "vector": vectors[j]}
                if payloads and payloads[j]:
                    doc.update(payloads[j])
                batch.append(doc)
            lsn = self._col().upsert(batch)
            if lsn:
                self._last_write_lsn = lsn

    def search(  # type: ignore[override]
        self,
        query: str,
        vectors: List[float],
        top_k: int = 5,
        filters: Optional[Dict] = None,
    ) -> List[OutputData]:
        q = select(*self._select_fields(filters), score=fn.vector_distance("vector", vectors))
        if filters:
            q = q.filter(self._convert_filters(filters))
        hits = self._col().query(q.topk(field("score"), top_k, asc=self._search_asc()), lsn=self._last_write_lsn)
        return [
            OutputData(id=str(h["_id"]), score=self._to_similarity(h["score"]), payload=self._payload_from(h))
            for h in hits
        ]

    def keyword_search(  # type: ignore[override]
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict] = None,
    ) -> List[OutputData]:
        """Native BM25 keyword search over the lemmatized text."""
        q = topk_filter(match(query, field="text_lemmatized")).select(*self._select_fields(filters), score=fn.bm25_score())
        if filters:
            q = q.filter(self._convert_filters(filters))
        try:
            hits = self._col().query(q.topk(field("score"), top_k, asc=False), lsn=self._last_write_lsn)
        except InvalidArgumentError:
            logger.warning(
                "keyword_search unavailable: collection has no keyword index on 'text_lemmatized'; "
                "returning no keyword results."
            )
            return []
        # BM25 scores are already higher = better; Mem0 core normalizes them itself.
        return [OutputData(id=str(h["_id"]), score=float(h["score"]), payload=self._payload_from(h)) for h in hits]

    def delete(self, vector_id: Union[str, int]):
        lsn = self._col().delete([str(vector_id)])
        if lsn:
            self._last_write_lsn = lsn

    def update(
        self,
        vector_id: Union[str, int],
        vector: Optional[List[float]] = None,
        payload: Optional[Dict] = None,
    ):
        doc: Dict[str, Any] = {"_id": str(vector_id)}
        if vector is not None:
            doc["vector"] = vector
        if payload:
            doc.update(payload)
        lsn = self._col().upsert([doc])
        if lsn:
            self._last_write_lsn = lsn

    def get(self, vector_id: Union[str, int]) -> Optional[OutputData]:  # type: ignore[override]
        results = self._col().get([str(vector_id)], lsn=self._last_write_lsn)
        doc = (results or {}).get(str(vector_id))
        if doc is None:
            return None
        return OutputData(id=str(vector_id), score=None, payload=self._payload_from(doc))

    def list_cols(self) -> List[str]:  # type: ignore[override]
        return [c.name for c in self.client.collections().list()]

    def delete_col(self):
        try:
            if self.partition:
                self._col().delete_partition(self.partition)
            else:
                self.client.collections().delete(self.collection_name)
        except CollectionNotFoundError:
            pass
        self._last_write_lsn = None

    def col_info(self) -> Dict:  # type: ignore[override]
        try:
            col = self.client.collections().get(self.collection_name)
            count = self._col().count()
            return {"name": col.name, "count": count, "region": col.region}
        except Exception:
            return {"name": self.collection_name}

    def list(self, filters: Optional[Dict] = None, top_k: int = 100) -> List[List[OutputData]]:  # type: ignore[override]
        q = select(*self._select_fields(filters))
        if filters:
            q = q.filter(self._convert_filters(filters))
        hits = self._col().query(q.limit(top_k), lsn=self._last_write_lsn)
        return [[OutputData(id=str(h["_id"]), score=None, payload=self._payload_from(h)) for h in hits]]

    def reset(self):
        self.delete_col()
        self.create_col(self.collection_name, self.embedding_model_dims, self.distance_metric)

    @staticmethod
    def _generate_random_user_id() -> str:
        return secrets.token_urlsafe(16)

    def _ensure_migrations_collection(self) -> None:
        try:
            self.client.collections().create(
                _MIGRATIONS_COLLECTION_NAME,
                schema={"user_id": text().required()},
            )
        except CollectionAlreadyExistsError:
            pass

    def get_user_id(self) -> str:
        if self._cached_user_id:
            return self._cached_user_id

        self._ensure_migrations_collection()
        results = self.client.collection(_MIGRATIONS_COLLECTION_NAME).get([_USER_ID_RECORD_ID])
        doc = (results or {}).get(_USER_ID_RECORD_ID)
        if doc and doc.get("user_id"):
            self._cached_user_id = doc["user_id"]
            return self._cached_user_id

        user_id = self._generate_random_user_id()
        self.client.collection(_MIGRATIONS_COLLECTION_NAME).upsert(
            [{"_id": _USER_ID_RECORD_ID, "user_id": user_id}]
        )
        self._cached_user_id = user_id
        return user_id

    def set_user_id(self, user_id: str) -> None:
        self._ensure_migrations_collection()
        self.client.collection(_MIGRATIONS_COLLECTION_NAME).upsert(
            [{"_id": _USER_ID_RECORD_ID, "user_id": user_id}]
        )
        self._cached_user_id = user_id
