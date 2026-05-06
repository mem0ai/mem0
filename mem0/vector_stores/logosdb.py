"""LogosDB vector store adapter for mem0.

LogosDB is a local, zero-infrastructure HNSW vector database that stores its
index in memory-mapped files on disk — no server process required.

Install::

    pip install "logosdb[mem0]"

Usage::

    from mem0 import Memory

    config = {
        "vector_store": {
            "provider": "logosdb",
            "config": {
                "collection_name": "mem0",
                "path": "/data/mem0",
                "embedding_model_dims": 1536,
            },
        }
    }
    m = Memory.from_config(config)
    m.add("I prefer Python over JavaScript", user_id="alice")
    memories = m.get_all(user_id="alice")
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

try:
    import numpy as np
    from logosdb import DB, DIST_COSINE
except ImportError:
    raise ImportError(
        "LogosDB requires extra dependencies. Install with: pip install logosdb"
    ) from None

from mem0.vector_stores.base import VectorStoreBase


class OutputData:
    """Minimal hit object that matches mem0's expected search result shape."""

    __slots__ = ("id", "score", "payload")

    def __init__(self, id: str, score: float, payload: Dict[str, Any]) -> None:
        self.id = id
        self.score = score
        self.payload = payload


class LogosDB(VectorStoreBase):
    """mem0 VectorStoreBase implementation backed by LogosDB.

    Each mem0 collection maps to a sub-directory of *path*.  Collections are
    opened lazily and kept open for the lifetime of the instance.

    Args:
        collection_name:   Default collection name (mem0 may override per-call).
        path:              Root directory where collection sub-directories live.
        embedding_model_dims: Embedding vector dimension.
        distance_metric:   ``"cosine"`` (default) or ``"l2"``.
        max_elements:      HNSW index capacity per collection.
        ef_construction:   HNSW build-time parameter.
        M:                 HNSW graph out-degree.
        ef_search:         HNSW query-time parameter.
    """

    def __init__(
        self,
        collection_name: str = "mem0",
        path: str = "/tmp/logosdb",
        embedding_model_dims: int = 1536,
        distance_metric: str = "cosine",
        max_elements: int = 1_000_000,
        ef_construction: int = 200,
        M: int = 16,
        ef_search: int = 50,
    ) -> None:
        self._root = path
        self._default_col = collection_name
        self._dim = embedding_model_dims
        self._distance = DIST_COSINE if distance_metric == "cosine" else 2  # DIST_L2
        self._max_elements = max_elements
        self._ef_construction = ef_construction
        self._M = M
        self._ef_search = ef_search

        # Registry of open DB handles and their UUID → row_id maps.
        self._dbs: Dict[str, DB] = {}
        self._id_maps: Dict[str, Dict[int, str]] = {}  # row_id → external uuid

        os.makedirs(self._root, exist_ok=True)

    # ── Internal helpers ───────────────────────────────────────────────────

    def _col_path(self, name: str) -> str:
        return os.path.join(self._root, name)

    def _open(self, name: str) -> DB:
        if name not in self._dbs:
            path = self._col_path(name)
            os.makedirs(path, exist_ok=True)
            self._dbs[name] = DB(
                path=path,
                dim=self._dim,
                max_elements=self._max_elements,
                ef_construction=self._ef_construction,
                M=self._M,
                ef_search=self._ef_search,
                distance=self._distance,
            )
            self._id_maps[name] = {}
        return self._dbs[name]

    def _resolve(self, name: Optional[str]) -> str:
        return name if name else self._default_col

    # ── VectorStoreBase interface ──────────────────────────────────────────

    def create_col(
        self,
        name: str,
        vector_size: int,
        distance: Any = None,
    ) -> None:
        """Create (or open) a collection. Collections are created lazily on first insert."""
        self._open(name)

    def insert(
        self,
        name: str,
        vectors: List[List[float]],
        payloads: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
    ) -> None:
        """Insert vectors with optional payloads and external UUIDs."""
        db = self._open(name)
        id_map = self._id_maps[name]

        if payloads is None:
            payloads = [{} for _ in vectors]
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in vectors]

        for ext_id, vec_list, payload in zip(ids, vectors, payloads):
            vec = np.asarray(vec_list, dtype=np.float32)
            text = str(payload.get("data", payload.get("text", "")))
            ts = str(payload.get("created_at", ""))
            row_id = int(db.put(vec, text=text, timestamp=ts))
            id_map[row_id] = ext_id

    def search(
        self,
        name: str,
        query: List[float],
        limit: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[OutputData]:
        """Approximate nearest-neighbour search. Returns ranked OutputData hits."""
        db = self._open(name)
        id_map = self._id_maps[name]
        qvec = np.asarray(query, dtype=np.float32)
        hits = db.search(qvec, top_k=limit)
        results: List[OutputData] = []
        for h in hits:
            ext_id = id_map.get(h.id, str(h.id))
            payload: Dict[str, Any] = {}
            if h.text:
                payload["data"] = h.text
            if h.timestamp:
                payload["created_at"] = h.timestamp
            results.append(OutputData(id=ext_id, score=float(h.score), payload=payload))
        return results

    def delete(self, name: str, vector_id: str) -> None:
        """Delete a vector by its external UUID."""
        db = self._open(name)
        id_map = self._id_maps[name]
        row_id = next((rid for rid, uid in id_map.items() if uid == vector_id), None)
        if row_id is not None:
            db.delete(row_id)
            del id_map[row_id]

    def update(
        self,
        name: str,
        vector_id: str,
        vector: Optional[List[float]] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update a vector entry (tombstone + re-insert)."""
        db = self._open(name)
        id_map = self._id_maps[name]
        row_id = next((rid for rid, uid in id_map.items() if uid == vector_id), None)
        if row_id is None:
            return

        p = payload or {}
        text = str(p.get("data", ""))
        ts = str(p.get("created_at", ""))

        if vector is not None:
            vec = np.asarray(vector, dtype=np.float32)
        else:
            # Keep existing vector — delete and re-insert with same payload
            db.delete(row_id)
            del id_map[row_id]
            logger.warning("LogosDB: update without new vector re-inserts with empty vector")
            return

        new_row_id = int(db.update(row_id, vec, text=text, timestamp=ts))
        del id_map[row_id]
        id_map[new_row_id] = vector_id

    def get(self, name: str, vector_id: str) -> Optional[OutputData]:
        """Retrieve a single entry by its external UUID."""
        id_map = self._id_maps.get(name, {})
        row_id = next((rid for rid, uid in id_map.items() if uid == vector_id), None)
        if row_id is None:
            return None
        return OutputData(id=vector_id, score=1.0, payload={"row_id": row_id})

    def list_cols(self) -> List[str]:
        """List all collection names (sub-directories under root)."""
        try:
            return [
                d
                for d in os.listdir(self._root)
                if os.path.isdir(os.path.join(self._root, d))
            ]
        except FileNotFoundError:
            return []

    def delete_col(self, name: str) -> None:
        """Close and remove a collection from the in-process registry."""
        if name in self._dbs:
            self._dbs[name].close()
            del self._dbs[name]
            del self._id_maps[name]

    def col_info(self, name: str) -> Dict[str, Any]:
        """Return stats for a collection."""
        db = self._open(name)
        return {
            "name": name,
            "count": int(db.count()),
            "dim": self._dim,
            "path": self._col_path(name),
        }

    def reset(self) -> None:
        """Close all open collections."""
        for db in self._dbs.values():
            try:
                db.close()
            except Exception:
                pass
        self._dbs.clear()
        self._id_maps.clear()

    def list(
        self,
        name: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> List[List[OutputData]]:
        """Return all vectors in a collection (wrapped in a list for mem0 compatibility)."""
        db = self._open(name)
        id_map = self._id_maps[name]
        count = int(db.count())
        if count == 0:
            return [[]]

        results: List[OutputData] = []
        for row_id, ext_id in id_map.items():
            results.append(OutputData(id=ext_id, score=1.0, payload={"row_id": row_id}))
            if limit is not None and len(results) >= limit:
                break

        return [results]
