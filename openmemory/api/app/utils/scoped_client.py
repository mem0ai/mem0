"""
ScopedMemoryClient: a thin wrapper around the mem0 client that captures user_id
in its constructor and injects it on every call.

Goal: make user_id isolation a property of the wrapper instance, so a future
tool author cannot accidentally call mem0 without scoping. Every memory
operation in OpenMemory should go through this wrapper, never through the
underlying client directly.

When mem0 changes which call shape it requires (top-level entity kwargs vs
filters dict), only the methods on this class need updating, not every tool
or route.

Methods exposed:

    .add(text, *, metadata=None, infer=True)   -> dict
    .search(query, *, top_k=10)                -> list[OutputData]
    .get_all(*, top_k=1000)                    -> dict with "results" key
    .delete(memory_id)                         -> None
"""

from __future__ import annotations

from typing import Any, Optional


class ScopedMemoryClient:
    """User-scoped wrapper around the mem0 Memory client.

    Construct with an already-initialized mem0 client and a non-empty user_id.
    Every call routes the user_id into the parameter shape mem0 currently
    requires for that operation.
    """

    def __init__(self, client: Any, user_id: str) -> None:
        if not user_id:
            raise ValueError("ScopedMemoryClient requires a non-empty user_id")
        if client is None:
            raise ValueError("ScopedMemoryClient requires an initialized memory client")
        self._client = client
        self._user_id = user_id

    @property
    def user_id(self) -> str:
        return self._user_id

    @property
    def filters(self) -> dict[str, str]:
        """Filter dict suitable for mem0 operations that require `filters=`."""
        return {"user_id": self._user_id}

    def add(
        self,
        text: str,
        *,
        metadata: Optional[dict] = None,
        infer: bool = True,
    ) -> Any:
        """Add a memory. mem0's add() still accepts top-level user_id."""
        return self._client.add(
            text,
            user_id=self._user_id,
            metadata=metadata or {},
            infer=infer,
        )

    def search(self, query: str, *, top_k: int = 10) -> Any:
        """Vector-store search scoped to this user.

        Mirrors the existing pattern in mcp_server.search_memory: embed the
        query with the configured embedder, then call vector_store.search
        with the user_id filter.
        """
        embeddings = self._client.embedding_model.embed(query, "search")
        return self._client.vector_store.search(
            query=query,
            vectors=embeddings,
            top_k=top_k,
            filters=self.filters,
        )

    def get_all(self, *, top_k: int = 1000) -> Any:
        """List all memories for this user. Returns a dict with `results`."""
        return self._client.get_all(filters=self.filters, top_k=top_k)

    def delete(self, memory_id: str) -> Any:
        """Delete a single memory by id.

        mem0's delete is by-id and does not accept a filter. Callers must
        verify the memory_id belongs to this user before calling — typically
        by checking against the SQL Memory table for this user_id and the
        app's ACL. The wrapper does not enforce that here because the
        access-control check needs the SQLAlchemy session.
        """
        return self._client.delete(memory_id)
