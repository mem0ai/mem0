"""Dakera vector store backend for mem0.

Dakera (https://dakera.ai) is a self-hosted, decay-weighted memory server that
manages its own embedding pipeline. This integration lets mem0 use Dakera as a
drop-in vector store so that all agent memory benefits from Dakera's importance
weighting, recency decay, and semantic deduplication — without requiring a
separate embedding service.

Quick-start:
    docker run -d -p 3300:3300 -e DAKERA_API_KEY=demo \\
        ghcr.io/dakera-ai/dakera:latest

Usage with mem0:
    from mem0 import Memory

    config = {
        "vector_store": {
            "provider": "dakera",
            "config": {
                "url": "http://localhost:3300",
                "api_key": "demo",       # match DAKERA_API_KEY
                "collection_name": "my-agent",
            },
        }
    }
    m = Memory.from_config(config)
    m.add("The user prefers dark mode", user_id="alice")
    results = m.search("UI preferences", user_id="alice")
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:
    raise ImportError(
        "The 'requests' library is required for the Dakera vector store. "
        "Install it with: pip install requests"
    )

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)


class OutputData:
    """Minimal result object matching the shape expected by mem0's memory layer."""

    __slots__ = ("id", "score", "payload")

    def __init__(self, id: Optional[str], score: Optional[float], payload: Optional[Dict]):
        self.id = id
        self.score = score
        self.payload = payload


class DakeraVectorStore(VectorStoreBase):
    """mem0 vector store backed by a self-hosted Dakera memory server.

    Dakera handles embedding internally, so this adapter skips the vector
    arguments that mem0 passes for other backends and instead submits plain-text
    queries directly to Dakera's semantic search endpoint.

    Args:
        collection_name: Agent-ID namespace used to isolate memories. Defaults
            to ``"mem0"``.
        url: Base URL of the Dakera server. Defaults to
            ``"http://localhost:3300"``.
        api_key: API key for the Dakera server. Required when the server was
            started with ``DAKERA_API_KEY`` set.
        embedding_model_dims: Accepted for compatibility with mem0 internals;
            Dakera owns its embedding model so this value is ignored.
    """

    def __init__(
        self,
        collection_name: str = "mem0",
        url: str = "http://localhost:3300",
        api_key: Optional[str] = None,
        embedding_model_dims: Optional[int] = None,
        **_kwargs: Any,
    ) -> None:
        self.collection_name = collection_name
        self._base_url = url.rstrip("/")
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})
        if api_key:
            self._session.headers.update({"Authorization": f"Bearer {api_key}"})

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _post(self, path: str, body: Dict) -> Dict:
        url = f"{self._base_url}{path}"
        try:
            resp = self._session.post(url, json=body, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("DakeraVectorStore: POST %s failed — %s", path, exc)
            return {}

    def _get(self, path: str) -> Dict:
        url = f"{self._base_url}{path}"
        try:
            resp = self._session.get(url, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("DakeraVectorStore: GET %s failed — %s", path, exc)
            return {}

    def _put(self, path: str, body: Dict) -> Dict:
        url = f"{self._base_url}{path}"
        try:
            resp = self._session.put(url, json=body, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("DakeraVectorStore: PUT %s failed — %s", path, exc)
            return {}

    def _recall_to_output(self, results: List[Dict]) -> List[OutputData]:
        """Convert Dakera RecallResult list to mem0 OutputData list."""
        output = []
        for r in results:
            memory = r.get("memory", {})
            output.append(
                OutputData(
                    id=memory.get("id"),
                    score=r.get("score"),
                    payload={"data": memory.get("content", ""), **(memory.get("metadata") or {})},
                )
            )
        return output

    # ------------------------------------------------------------------
    # VectorStoreBase required methods
    # ------------------------------------------------------------------

    def create_col(self, name: str, vector_size: Optional[int] = None, distance: Optional[str] = None) -> None:
        """No-op — Dakera creates namespaces on first write."""
        self.collection_name = name or self.collection_name

    def insert(
        self,
        vectors: List[List[float]],
        payloads: Optional[List[Dict]] = None,
        ids: Optional[List[str]] = None,
    ) -> None:
        """Store memories in Dakera. Vectors are ignored (Dakera embeds internally).

        mem0 passes ``payloads[i]["data"]`` as the text content to persist.
        """
        payloads = payloads or [{}] * len(vectors)
        ids = ids or [str(uuid.uuid4()) for _ in vectors]
        for payload, mem_id in zip(payloads, ids):
            content = payload.get("data") or payload.get("content") or ""
            if not content:
                continue
            body: Dict = {
                "content": content,
                "agent_id": self.collection_name,
            }
            # Forward optional fields from payload through to Dakera
            if "session_id" in payload:
                body["session_id"] = payload["session_id"]
            extra_meta = {k: v for k, v in payload.items() if k not in ("data", "content", "session_id")}
            if extra_meta:
                body["metadata"] = extra_meta
            self._post("/v1/memory/store", body)

    def search(
        self,
        query: str,
        vectors: Optional[List[float]] = None,
        top_k: int = 5,
        filters: Optional[Dict] = None,
    ) -> List[OutputData]:
        """Semantic recall from Dakera using the query text.

        The ``vectors`` argument is intentionally ignored — Dakera embeds the
        query server-side, which produces better results because it uses the same
        embedding model that was used during ingestion.
        """
        body: Dict = {
            "agent_id": self.collection_name,
            "query": query,
            "top_k": top_k,
        }
        if filters and "session_id" in filters:
            body["session_id"] = filters["session_id"]
        data = self._post("/v1/memory/search", body)
        return self._recall_to_output(data.get("memories", []))

    def delete(self, vector_id: str) -> None:
        """Delete a single memory by ID."""
        self._post(
            "/v1/memory/forget",
            {"agent_id": self.collection_name, "memory_ids": [vector_id]},
        )

    def update(
        self,
        vector_id: str,
        vector: Optional[List[float]] = None,
        payload: Optional[Dict] = None,
    ) -> None:
        """Update the text content of an existing memory.

        The ``vector`` argument is ignored — Dakera re-embeds the updated content.
        """
        if not payload:
            return
        content = payload.get("data") or payload.get("content")
        if not content:
            return
        self._put(f"/v1/memory/update/{vector_id}", {"content": content})

    def get(self, vector_id: str) -> Optional[OutputData]:
        """Retrieve a single memory by ID."""
        data = self._get(f"/v1/memory/get/{vector_id}")
        memory = data.get("memory")
        if not memory:
            return None
        return OutputData(
            id=memory.get("id"),
            score=1.0,
            payload={"data": memory.get("content", ""), **(memory.get("metadata") or {})},
        )

    def list_cols(self) -> List[str]:
        """Return the current agent namespace as the sole 'collection'."""
        return [self.collection_name]

    def delete_col(self) -> None:
        """Delete all memories in the current agent namespace."""
        self._post(
            "/v1/memory/forget",
            {"agent_id": self.collection_name},
        )

    def col_info(self) -> Dict:
        """Return basic info about the current agent namespace."""
        return {"name": self.collection_name, "provider": "dakera"}

    def list(
        self,
        filters: Optional[Dict] = None,
        top_k: Optional[int] = None,
    ) -> List[OutputData]:
        """Retrieve all memories in the namespace, optionally filtered by session."""
        body: Dict = {
            "agent_id": self.collection_name,
            "query": None,
            "top_k": top_k or 100,
        }
        if filters and "session_id" in filters:
            body["session_id"] = filters["session_id"]
        data = self._post("/v1/memory/search", body)
        return self._recall_to_output(data.get("memories", []))

    def reset(self) -> None:
        """Delete all memories and start fresh."""
        self.delete_col()

    def keyword_search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict] = None,
    ) -> List[OutputData]:
        """BM25 full-text search via Dakera's hybrid routing mode."""
        body: Dict = {
            "agent_id": self.collection_name,
            "query": query,
            "top_k": top_k,
            "routing": "bm25",
        }
        if filters and "session_id" in filters:
            body["session_id"] = filters["session_id"]
        data = self._post("/v1/memory/search", body)
        return self._recall_to_output(data.get("memories", []))

    def search_batch(
        self,
        queries: List[str],
        vectors_list: Optional[List[List[float]]] = None,
        top_k: int = 1,
        filters: Optional[Dict] = None,
    ) -> List[List[OutputData]]:
        """Batch search — delegates to Dakera's batch recall endpoint."""
        results = []
        for query in queries:
            results.append(self.search(query, top_k=top_k, filters=filters))
        return results
