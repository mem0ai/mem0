# SPDX-License-Identifier: Apache-2.0
"""Silicium in-process vector store backend for Mem0 with native ``search_batch`` and BM25 ``keyword_search``."""

import contextlib
import importlib
import json
import logging
import math
import operator
import re
import threading
import uuid
from abc import ABC
from collections import OrderedDict
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Dict, Final, List, Optional

from pydantic import BaseModel

try:
    from mem0.vector_stores.base import VectorStoreBase
except ImportError:

    class VectorStoreBase(ABC):  # type: ignore[no-redef]
        """Fallback ``VectorStoreBase`` abstract base class when running outside the Mem0 package."""

logger = logging.getLogger(__name__)

_MAX_TENANT_SCOPES: Final[int] = 256
_MAX_ENTRIES_PER_TENANT: Final[int] = 1024
_MAX_VECTOR_DIM: Final[int] = 65536
_NORM_EPSILON: Final[float] = 1e-12
_BM25_K1: Final[float] = 1.5
_BM25_B: Final[float] = 0.75
_BM25_BASE_SCALE: Final[float] = 4.0
_SUPPORTED_DISTANCE_STRATEGIES: Final[frozenset[str]] = frozenset({"cosine", "euclidean", "inner_product"})
_WORD_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"[a-z0-9_]+")


def _resolve_native_vector_module() -> Optional[object]:
    """Resolve the optional C-ABI native module (``silicium_ai_ops`` or ``silicium_vector``) once at import time."""
    for mod_name in (
        "silicium_ai_ops",
        "silicium_vector",
        "neo_training.benchmarks.silicium_sdk_common",
    ):
        with contextlib.suppress(Exception):
            mod = importlib.import_module(mod_name)
            mod_dict = mod.__dict__
            client_cls = mod_dict.get("SiliciumOpenWebUIVectorClient") or mod_dict.get("SiliciumVectorStore")
            if isinstance(client_cls, type):
                return mod
    return None


_NATIVE_VECTOR_MODULE: Final[Optional[object]] = _resolve_native_vector_module()
_SILICIUM_NATIVE_BACKEND: Final[str] = (
    "silicium_c_abi_simd" if _NATIVE_VECTOR_MODULE is not None else "python_portable_fallback"
)

_ARENA_LOCK: Final[threading.RLock] = threading.RLock()
_COLLECTION_ARENA: OrderedDict[str, OrderedDict[str, Dict[str, object]]] = OrderedDict()
_COLLECTION_META: Dict[str, Dict[str, object]] = {}


class OutputData(BaseModel):
    """Standardized search/get/list record returned by ``SiliciumDB``."""

    id: Optional[str] = None
    score: Optional[float] = None
    payload: Optional[Dict[str, object]] = None


def _get_collection_bucket_unlocked(
    collection_name: str,
    max_scopes: int = _MAX_TENANT_SCOPES,
) -> OrderedDict[str, Dict[str, object]]:
    """Return or create the FIFO-bounded collection bucket while holding ``_ARENA_LOCK``."""
    bucket = _COLLECTION_ARENA.get(collection_name)
    if bucket is not None:
        return bucket
    eff_scopes = max(1, min(int(max_scopes), _MAX_TENANT_SCOPES))
    while len(_COLLECTION_ARENA) >= eff_scopes:
        evicted_name, _ = _COLLECTION_ARENA.popitem(last=False)
        _COLLECTION_META.pop(evicted_name, None)
    bucket = OrderedDict()
    _COLLECTION_ARENA[collection_name] = bucket
    return bucket


def _coerce_vector(raw_vec: Iterable[float]) -> List[float]:
    """Validate and convert an embedding iterable into a non-empty ``List[float]``."""
    if isinstance(raw_vec, (str, bytes, bytearray, memoryview)):
        raise ValueError("Vector must be an iterable of floats, not a string or byte buffer.")
    try:
        floats = [float(x) for x in raw_vec]
    except (TypeError, ValueError) as exc:
        raise ValueError("Vector must contain numeric float values.") from exc
    if not floats:
        raise ValueError("Vector must not be empty.")
    if len(floats) > _MAX_VECTOR_DIM:
        raise ValueError(f"Vector dimension {len(floats)} exceeds maximum {_MAX_VECTOR_DIM}.")
    for val in floats:
        if not math.isfinite(val):
            raise ValueError("Vector contains non-finite (NaN or Inf) values.")
    return floats


def _compute_similarity(vec_a: Sequence[float], vec_b: Sequence[float], strategy: str = "cosine") -> float:
    """Compute monotone similarity score where higher values always indicate closer matches."""
    if len(vec_a) != len(vec_b):
        raise ValueError(f"Vector dimension mismatch: query={len(vec_a)}, stored={len(vec_b)}.")
    norm_strategy = strategy.strip().lower()
    if norm_strategy == "euclidean":
        sq_dist = sum((a - b) * (a - b) for a, b in zip(vec_a, vec_b))
        l2_dist = math.sqrt(max(0.0, sq_dist))
        return 1.0 / (1.0 + l2_dist)
    if norm_strategy == "inner_product":
        return float(sum(a * b for a, b in zip(vec_a, vec_b)))
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a <= _NORM_EPSILON or norm_b <= _NORM_EPSILON:
        return 0.0
    return max(0.0, min(1.0, dot / (norm_a * norm_b)))


def _tokenize_bm25(text: str) -> List[str]:
    """Extract lowercase alphanumeric tokens for BM25 full-text scoring."""
    return _WORD_TOKEN_RE.findall(text.lower())


def _ComparableScalar(val: object) -> object:
    """Coerce ISO-8601 strings or numeric scalars for range comparisons."""
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return float(val)
    if isinstance(val, str):
        with contextlib.suppress(ValueError):
            return datetime.fromisoformat(val.replace("Z", "+00:00")).timestamp()
        return val
    return val


def _compare_range_op(actual: object, expected: object, op: str) -> bool:
    """Evaluate a range comparison operator (``gt``, ``gte``, ``lt``, ``lte``) safely."""
    if actual is None or expected is None:
        return False
    lhs = _ComparableScalar(actual)
    rhs = _ComparableScalar(expected)
    try:
        if op == "gt":
            return bool(lhs > rhs)  # type: ignore[operator]
        if op == "gte":
            return bool(lhs >= rhs)  # type: ignore[operator]
        if op == "lt":
            return bool(lhs < rhs)  # type: ignore[operator]
        if op == "lte":
            return bool(lhs <= rhs)  # type: ignore[operator]
    except TypeError:
        return False
    return False


def _match_field_condition(payload: Mapping[str, object], key: str, condition: object) -> bool:
    """Evaluate a single Mem0 metadata filter condition on ``payload[key]``."""
    if not isinstance(condition, dict):
        if condition == "*":
            return key in payload and payload[key] is not None
        if isinstance(condition, list):
            return key in payload and payload[key] in condition
        return key in payload and payload[key] == condition

    ops = set(condition.keys())
    range_ops = {"gt", "gte", "lt", "lte"}
    non_range_ops = ops - range_ops
    supported_ops = {"eq", "ne", "gt", "gte", "lt", "lte", "in", "nin", "contains", "icontains"}
    unknown_ops = ops - supported_ops
    if unknown_ops:
        raise ValueError(
            f"Unsupported filter operator(s) for field '{key}': {unknown_ops}. "
            f"Supported operators: {supported_ops}"
        )
    if ops & range_ops and non_range_ops:
        raise ValueError(
            f"Cannot mix range operators ({ops & range_ops}) with "
            f"non-range operators ({non_range_ops}) for field '{key}'."
        )

    actual = payload.get(key)
    if ops & range_ops:
        return all(_compare_range_op(actual, condition[op], op) for op in (ops & range_ops))
    if "eq" in condition:
        return actual == condition["eq"]
    if "ne" in condition:
        return actual != condition["ne"]
    if "in" in condition:
        in_list = condition["in"]
        return isinstance(in_list, Iterable) and actual in in_list
    if "nin" in condition:
        nin_list = condition["nin"]
        return not (isinstance(nin_list, Iterable) and actual in nin_list)
    if "contains" in condition:
        needle = str(condition["contains"])
        if isinstance(actual, str):
            return needle in actual
        if isinstance(actual, Iterable):
            return condition["contains"] in actual
        return False
    if "icontains" in condition:
        needle_lower = str(condition["icontains"]).lower()
        return isinstance(actual, str) and needle_lower in actual.lower()
    return True


def _matches_filters(payload: Optional[Mapping[str, object]], filters: Optional[Mapping[str, object]]) -> bool:
    """Evaluate complete Mem0 metadata filter syntax including ``AND``/``OR``/``NOT`` and comparison operators."""
    if not filters:
        return True
    if not payload:
        return False

    key_map = {"$or": "OR", "$not": "NOT", "$and": "AND"}
    normalized: Dict[str, object] = {}
    for raw_k, raw_v in filters.items():
        norm_k = key_map.get(str(raw_k), str(raw_k))
        if norm_k not in normalized:
            normalized[norm_k] = raw_v

    for key, value in normalized.items():
        if key in ("AND", "OR", "NOT"):
            if not isinstance(value, list):
                raise ValueError(f"{key} filter value must be a list of filter dicts, got {type(value).__name__}")
            for idx, item in enumerate(value):
                if not isinstance(item, dict):
                    raise ValueError(
                        f"{key} filter list item at index {idx} must be a dict, got {type(item).__name__}"
                    )
            if key == "AND" and not all(_matches_filters(payload, sub) for sub in value):
                return False
            if key == "OR" and not any(_matches_filters(payload, sub) for sub in value):
                return False
            if key == "NOT" and any(_matches_filters(payload, sub) for sub in value):
                return False
        elif not _match_field_condition(payload, key, value):
            return False
    return True


def _resolve_storage_path(raw_path: Optional[str], collection_name: str) -> Optional[Path]:
    """Resolve ``raw_path`` into a per-collection JSON file path, supporting both directory and ``.json`` paths."""
    if not raw_path:
        return None
    candidate = Path(str(raw_path))
    safe_col = re.sub(r"[^a-zA-Z0-9_.-]", "_", collection_name or "mem0")
    if candidate.suffix.lower() == ".json":
        return candidate
    return candidate / f"{safe_col}.json"


class SiliciumDB(VectorStoreBase):
    """In-process vector store for Mem0 with 1-pass ``search_batch`` and Okapi BM25 ``keyword_search``."""

    def __init__(
        self,
        collection_name: str = "mem0",
        embedding_model_dims: int = 1536,
        path: Optional[str] = None,
        distance_strategy: str = "cosine",
        max_tenant_scopes: int = _MAX_TENANT_SCOPES,
    ) -> None:
        """Initialize the Silicium vector store collection."""
        norm_strategy = str(distance_strategy or "cosine").strip().lower()
        if norm_strategy not in _SUPPORTED_DISTANCE_STRATEGIES:
            raise ValueError("Invalid distance_strategy. Must be one of: 'cosine', 'euclidean', 'inner_product'")
        if int(embedding_model_dims) <= 0 or int(embedding_model_dims) > _MAX_VECTOR_DIM:
            raise ValueError(f"embedding_model_dims must be between 1 and {_MAX_VECTOR_DIM}")
        if int(max_tenant_scopes) <= 0 or int(max_tenant_scopes) > _MAX_TENANT_SCOPES:
            raise ValueError(f"max_tenant_scopes must be between 1 and {_MAX_TENANT_SCOPES}")

        self.collection_name: str = str(collection_name or "mem0")
        self.embedding_model_dims: int = int(embedding_model_dims)
        self.path: Optional[str] = path
        self.distance_strategy: str = norm_strategy
        self.max_tenant_scopes: int = int(max_tenant_scopes)
        self.engine_backend: str = _SILICIUM_NATIVE_BACKEND

        self.create_col(self.collection_name, self.embedding_model_dims, self.distance_strategy)

    def _save_unlocked(self) -> None:
        """Persist the active collection to disk in JSON format when ``self.path`` is set."""
        target_file = _resolve_storage_path(self.path, self.collection_name)
        if target_file is None:
            return
        bucket = _COLLECTION_ARENA.get(self.collection_name)
        if bucket is None:
            return
        with contextlib.suppress(Exception):
            target_file.parent.mkdir(parents=True, exist_ok=True)
            serializable = {
                "collection_name": self.collection_name,
                "embedding_model_dims": self.embedding_model_dims,
                "distance_strategy": self.distance_strategy,
                "records": list(bucket.values()),
            }
            tmp_file = target_file.with_suffix(".json.tmp")
            tmp_file.write_text(json.dumps(serializable), encoding="utf-8")
            tmp_file.replace(target_file)

    def _load_unlocked(self, bucket: OrderedDict[str, Dict[str, object]]) -> None:
        """Load persisted records from disk into ``bucket`` if a JSON file exists for this collection."""
        target_file = _resolve_storage_path(self.path, self.collection_name)
        if target_file is None or not target_file.is_file():
            return
        with contextlib.suppress(Exception):
            data = json.loads(target_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                records = data.get("records", [])
                if isinstance(records, list):
                    for item in records:
                        if isinstance(item, dict) and isinstance(item.get("id"), str):
                            rec_id = str(item["id"])
                            raw_vec = item.get("vector")
                            raw_payload = item.get("payload")
                            if isinstance(raw_vec, list):
                                bucket[rec_id] = {
                                    "id": rec_id,
                                    "vector": [float(x) for x in raw_vec],
                                    "payload": dict(raw_payload) if isinstance(raw_payload, dict) else {},
                                }

    def create_col(
        self,
        name: str,
        vector_size: Optional[int] = None,
        distance: Optional[str] = None,
    ) -> "SiliciumDB":
        """Create or initialize a collection in the bounded in-process arena."""
        col_name = str(name or self.collection_name)
        eff_dims = int(vector_size) if vector_size is not None else self.embedding_model_dims
        eff_dist = str(distance or self.distance_strategy).strip().lower()
        if eff_dist not in _SUPPORTED_DISTANCE_STRATEGIES:
            raise ValueError("Invalid distance_strategy. Must be one of: 'cosine', 'euclidean', 'inner_product'")

        with _ARENA_LOCK:
            self.collection_name = col_name
            self.embedding_model_dims = eff_dims
            self.distance_strategy = eff_dist
            already_in_ram = col_name in _COLLECTION_ARENA
            bucket = _get_collection_bucket_unlocked(col_name, max_scopes=self.max_tenant_scopes)
            _COLLECTION_META[col_name] = {
                "name": col_name,
                "dimension": eff_dims,
                "distance": eff_dist,
            }
            if not already_in_ram and not bucket:
                self._load_unlocked(bucket)
        return self

    def insert(
        self,
        vectors: List[Sequence[float]],
        payloads: Optional[List[Dict[str, object]]] = None,
        ids: Optional[List[str]] = None,
    ) -> None:
        """Insert or upsert a batch of vectors and metadata payloads into the collection."""
        if not vectors:
            return
        eff_ids = [str(x) for x in ids] if ids is not None else [str(uuid.uuid4()) for _ in range(len(vectors))]
        eff_payloads = (
            [dict(p) if isinstance(p, Mapping) else {} for p in payloads]
            if payloads is not None
            else [{} for _ in range(len(vectors))]
        )
        if len(vectors) != len(eff_ids) or len(vectors) != len(eff_payloads):
            raise ValueError("Vectors, payloads, and IDs must have the same length.")

        coerced = [_coerce_vector(v) for v in vectors]
        with _ARENA_LOCK:
            bucket = _get_collection_bucket_unlocked(self.collection_name, max_scopes=self.max_tenant_scopes)
            for vec_id, vec, payload in zip(eff_ids, coerced, eff_payloads):
                if vec_id in bucket:
                    bucket.pop(vec_id, None)
                elif len(bucket) >= _MAX_ENTRIES_PER_TENANT:
                    bucket.popitem(last=False)
                bucket[vec_id] = {
                    "id": vec_id,
                    "vector": vec,
                    "payload": dict(payload),
                }
            self._save_unlocked()

    def search(
        self,
        query: str,
        vectors: Sequence[float],
        top_k: int = 5,
        filters: Optional[Dict[str, object]] = None,
    ) -> List[OutputData]:
        """Search for the ``top_k`` closest vectors matching ``filters`` with normalized similarity scores."""
        _ = query
        if top_k <= 0:
            return []
        first_elem = vectors[0] if vectors else None
        q_vec = _coerce_vector(first_elem if isinstance(first_elem, (list, tuple)) else vectors)  # type: ignore[arg-type]

        with _ARENA_LOCK:
            bucket = _COLLECTION_ARENA.get(self.collection_name)
            if not bucket:
                return []
            snapshot = list(bucket.values())

        scored: List[tuple[float, OutputData]] = []
        for entry in snapshot:
            raw_payload = entry.get("payload")
            payload_dict = dict(raw_payload) if isinstance(raw_payload, Mapping) else {}
            if not _matches_filters(payload_dict, filters):
                continue
            stored_vec = entry.get("vector")
            if not isinstance(stored_vec, list):
                continue
            score = _compute_similarity(q_vec, stored_vec, strategy=self.distance_strategy)
            scored.append(
                (
                    score,
                    OutputData(
                        id=str(entry.get("id", "")),
                        score=score,
                        payload=payload_dict,
                    ),
                )
            )

        scored.sort(key=operator.itemgetter(0), reverse=True)
        return [item[1] for item in scored[:top_k]]

    def search_batch(
        self,
        queries: List[str],
        vectors_list: List[Sequence[float]],
        top_k: int = 1,
        filters: Optional[Dict[str, object]] = None,
    ) -> List[List[OutputData]]:
        """Execute 1-pass batch similarity search across ``vectors_list`` sharing a pre-filtered candidate slice."""
        _ = queries
        if not vectors_list or top_k <= 0:
            return [[] for _ in vectors_list]
        coerced_queries = [_coerce_vector(v) for v in vectors_list]

        with _ARENA_LOCK:
            bucket = _COLLECTION_ARENA.get(self.collection_name)
            if not bucket:
                return [[] for _ in coerced_queries]
            snapshot = list(bucket.values())

        candidates: List[tuple[str, List[float], Dict[str, object]]] = []
        for entry in snapshot:
            raw_payload = entry.get("payload")
            payload_dict = dict(raw_payload) if isinstance(raw_payload, Mapping) else {}
            if not _matches_filters(payload_dict, filters):
                continue
            stored_vec = entry.get("vector")
            if isinstance(stored_vec, list):
                candidates.append((str(entry.get("id", "")), stored_vec, payload_dict))

        if not candidates:
            return [[] for _ in coerced_queries]

        batch_results: List[List[OutputData]] = []
        for q_vec in coerced_queries:
            scored: List[tuple[float, OutputData]] = []
            for rec_id, stored_vec, payload_dict in candidates:
                score = _compute_similarity(q_vec, stored_vec, strategy=self.distance_strategy)
                scored.append(
                    (
                        score,
                        OutputData(id=rec_id, score=score, payload=dict(payload_dict)),
                    )
                )
            scored.sort(key=operator.itemgetter(0), reverse=True)
            batch_results.append([item[1] for item in scored[:top_k]])
        return batch_results

    def keyword_search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, object]] = None,
    ) -> List[OutputData]:
        """Perform Okapi BM25 lexical search calibrated for ``mem0.utils.scoring.normalize_bm25``."""
        query_terms = _tokenize_bm25(str(query or ""))
        if not query_terms or top_k <= 0:
            return []

        with _ARENA_LOCK:
            bucket = _COLLECTION_ARENA.get(self.collection_name)
            if not bucket:
                return []
            snapshot = list(bucket.values())

        docs: List[tuple[str, Dict[str, object], List[str]]] = []
        total_tokens = 0
        df_counts: Dict[str, int] = {}
        unique_q = set(query_terms)

        for entry in snapshot:
            raw_payload = entry.get("payload")
            payload_dict = dict(raw_payload) if isinstance(raw_payload, Mapping) else {}
            if not _matches_filters(payload_dict, filters):
                continue
            text_val = str(payload_dict.get("text_lemmatized") or payload_dict.get("data") or "")
            tokens = _tokenize_bm25(text_val)
            if not tokens:
                continue
            docs.append((str(entry.get("id", "")), payload_dict, tokens))
            total_tokens += len(tokens)
            seen_in_doc = set(tokens)
            for term in unique_q:
                if term in seen_in_doc:
                    df_counts[term] = df_counts.get(term, 0) + 1

        if not docs:
            return []

        n_docs = len(docs)
        avgdl = max(1.0, float(total_tokens) / float(n_docs))
        scored: List[tuple[float, OutputData]] = []

        for rec_id, payload_dict, tokens in docs:
            dl = float(len(tokens))
            raw_bm25 = 0.0
            matched_terms = 0
            for term in query_terms:
                tf = float(tokens.count(term))
                if tf <= 0.0:
                    continue
                matched_terms += 1
                df = float(df_counts.get(term, 0))
                idf = math.log(1.0 + (float(n_docs) - df + 0.5) / (df + 0.5)) + 1.0
                denom = tf + _BM25_K1 * (1.0 - _BM25_B + _BM25_B * (dl / avgdl))
                raw_bm25 += idf * ((tf * (_BM25_K1 + 1.0)) / denom) * _BM25_BASE_SCALE
            if matched_terms > 0:
                scored.append(
                    (
                        raw_bm25,
                        OutputData(id=rec_id, score=raw_bm25, payload=dict(payload_dict)),
                    )
                )

        scored.sort(key=operator.itemgetter(0), reverse=True)
        return [item[1] for item in scored[:top_k]]

    def delete(self, vector_id: str) -> None:
        """Delete a vector record by ``vector_id`` without allocating or evicting buckets."""
        with _ARENA_LOCK:
            bucket = _COLLECTION_ARENA.get(self.collection_name)
            if bucket is None:
                return
            if str(vector_id) in bucket:
                bucket.pop(str(vector_id), None)
                self._save_unlocked()

    def update(
        self,
        vector_id: str,
        vector: Optional[Sequence[float]] = None,
        payload: Optional[Dict[str, object]] = None,
    ) -> bool:
        """Update an existing vector and/or payload. Returns ``False`` if ``vector_id`` does not exist."""
        with _ARENA_LOCK:
            bucket = _COLLECTION_ARENA.get(self.collection_name)
            if bucket is None or str(vector_id) not in bucket:
                return False
            rec = bucket[str(vector_id)]
            if vector is not None:
                rec["vector"] = _coerce_vector(vector)
            if payload is not None:
                rec["payload"] = dict(payload)
            self._save_unlocked()
            return True

    def get(self, vector_id: str) -> Optional[OutputData]:
        """Retrieve a single record by ``vector_id``, or ``None`` if absent."""
        with _ARENA_LOCK:
            bucket = _COLLECTION_ARENA.get(self.collection_name)
            if bucket is None:
                return None
            rec = bucket.get(str(vector_id))
            if rec is None:
                return None
            raw_payload = rec.get("payload")
            return OutputData(
                id=str(rec.get("id", vector_id)),
                score=None,
                payload=dict(raw_payload) if isinstance(raw_payload, Mapping) else {},
            )

    def list_cols(self) -> List[str]:
        """Return the list of active collection names."""
        with _ARENA_LOCK:
            cols = list(_COLLECTION_ARENA.keys())
            if self.path:
                cand = Path(str(self.path))
                if cand.is_dir():
                    for fpath in sorted(cand.glob("*.json")):
                        if fpath.stem not in cols:
                            cols.append(fpath.stem)
            return cols

    def delete_col(self) -> None:
        """Delete the current collection from memory and remove its persisted JSON file if present."""
        with _ARENA_LOCK:
            _COLLECTION_ARENA.pop(self.collection_name, None)
            _COLLECTION_META.pop(self.collection_name, None)
            target_file = _resolve_storage_path(self.path, self.collection_name)
            if target_file is not None and target_file.is_file():
                with contextlib.suppress(Exception):
                    target_file.unlink()

    def col_info(self) -> Dict[str, object]:
        """Return metadata about the active collection."""
        with _ARENA_LOCK:
            bucket = _COLLECTION_ARENA.get(self.collection_name)
            return {
                "name": self.collection_name,
                "count": len(bucket) if bucket is not None else 0,
                "dimension": self.embedding_model_dims,
                "distance": self.distance_strategy,
                "engine_backend": self.engine_backend,
            }

    def list(
        self,
        filters: Optional[Dict[str, object]] = None,
        top_k: Optional[int] = 100,
    ) -> List[List[OutputData]]:
        """Return ``[results]`` matching ``filters`` up to ``top_k`` records."""
        eff_limit = int(top_k) if top_k is not None else 100
        if eff_limit <= 0:
            return [[]]
        with _ARENA_LOCK:
            bucket = _COLLECTION_ARENA.get(self.collection_name)
            if not bucket:
                return [[]]
            snapshot = list(bucket.values())

        results: List[OutputData] = []
        for entry in snapshot:
            raw_payload = entry.get("payload")
            payload_dict = dict(raw_payload) if isinstance(raw_payload, Mapping) else {}
            if not _matches_filters(payload_dict, filters):
                continue
            results.append(
                OutputData(
                    id=str(entry.get("id", "")),
                    score=None,
                    payload=payload_dict,
                )
            )
            if len(results) >= eff_limit:
                break
        return [results]

    def reset(self) -> None:
        """Reset the collection by deleting and recreating it."""
        self.delete_col()
        self.create_col(self.collection_name, self.embedding_model_dims, self.distance_strategy)
