"""A Strands ``MemoryStore`` backed by Mem0.

A memory store gives a Strands agent cross-session recall: a
:class:`~strands.memory.MemoryManager` searches it to recall facts and, when
writable, writes new ones -- either directly or via automatic extraction from the
conversation. Unlike the ``mem0_memory`` tool (which the model calls explicitly),
a store plugs into the agent loop out of the box, with memory injection and
extraction triggers handled by the manager.

``Mem0MemoryStore`` implements both write sinks, which is what sets it apart from a
vector-DB-style store:

- :meth:`add` writes a single distilled fact verbatim (``infer=False``). This is
  the sink for the ``add_memory`` tool and for a client-side extractor.
- :meth:`add_messages` hands raw conversation turns to Mem0 for **server-side
  extraction** (``infer=True``). Because this sink exists, enabling ``extraction``
  routes raw messages straight to Mem0's own extraction pipeline -- no extra
  client-side model call, and Mem0's server-side de-duplication applies.

Example:
    ```python
    from strands import Agent
    from strands.memory import MemoryManager
    from strands_mem0 import Mem0MemoryStore

    # Recall + write, with Mem0 extracting facts from the conversation server-side.
    store = Mem0MemoryStore(user_id="alex", writable=True, extraction=True)
    agent = Agent(memory_manager=MemoryManager(stores=[store]))
    ```

Configure the hosted platform via the ``api_key`` argument or the ``MEM0_API_KEY``
environment variable, or pass a Mem0 OSS ``config`` dict for a self-hosted backend.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from strands.memory import AddMessagesContext, MemoryEntry, MemoryStore, MemoryStoreConfig, SearchOptions
from strands.types.content import Message

from strands_mem0.client import Mem0ServiceClient

logger = logging.getLogger(__name__)

DEFAULT_MAX_SEARCH_RESULTS = 5
# Entity fields that scope a memory in Mem0. At least one must be set.
_SCOPE_FIELDS = ("user_id", "agent_id", "run_id", "app_id")


class Mem0MemoryStoreConfig(MemoryStoreConfig, total=False):
    """Configuration for a :class:`Mem0MemoryStore`.

    Extends the base :class:`~strands.memory.MemoryStoreConfig` (``name``,
    ``description``, ``max_search_results``, ``writable``, ``extraction``) with
    Mem0-specific fields.

    Attributes:
        user_id: Mem0 user namespace that owns the memories.
        agent_id: Mem0 agent namespace.
        run_id: Mem0 run/session namespace.
        app_id: Mem0 app namespace (platform only).
        metadata: Default metadata merged into every write.
        api_key: Mem0 platform API key. Defaults to ``$MEM0_API_KEY``.
        host: Mem0 platform base URL.
        config: Mem0 OSS config dict for a self-hosted backend.
    """

    user_id: str
    agent_id: str
    run_id: str
    app_id: str
    metadata: dict[str, Any]
    api_key: str
    host: str
    config: dict[str, Any]


class Mem0MemoryStore(MemoryStore):
    """A Strands :class:`~strands.memory.MemoryStore` backed by Mem0.

    Implements :meth:`search` (semantic recall), :meth:`add` (a verbatim
    single-fact write sink) and :meth:`add_messages` (raw-message ingestion with
    Mem0 server-side extraction). Because ``add_messages`` is implemented, enabling
    ``extraction`` uses Mem0's server-side extraction rather than a client-side
    model call.
    """

    def __init__(
        self,
        *,
        user_id: str | None = None,
        agent_id: str | None = None,
        run_id: str | None = None,
        app_id: str | None = None,
        name: str = "mem0",
        description: str | None = "Persistent long-term memory backed by Mem0.",
        max_search_results: int | None = None,
        writable: bool = True,
        extraction: Any = None,
        metadata: dict[str, Any] | None = None,
        api_key: str | None = None,
        host: str | None = None,
        config: dict[str, Any] | None = None,
        mem0_client: Any | None = None,
        client: Mem0ServiceClient | None = None,
    ) -> None:
        """Initialize the store.

        Args:
            user_id: Mem0 user namespace that owns the memories.
            agent_id: Mem0 agent namespace.
            run_id: Mem0 run/session namespace.
            app_id: Mem0 app namespace (platform only).
            name: Unique store identifier, used to target it in tools.
            description: Human-readable description, included in tool descriptions.
            max_search_results: Default maximum results per search.
            writable: Whether the store accepts writes.
            extraction: Automatic-extraction config (``bool | ExtractionConfig``).
            metadata: Default metadata merged into every write.
            api_key: Mem0 platform API key (defaults to ``$MEM0_API_KEY``).
            host: Mem0 platform base URL.
            config: Mem0 OSS config dict for a self-hosted backend.
            mem0_client: A pre-built raw Mem0 client (``mem0.MemoryClient`` or
                ``mem0.Memory``) to wrap, instead of constructing one from
                ``api_key`` / ``config``.
            client: A pre-built :class:`~strands_mem0.client.Mem0ServiceClient`
                (mainly for testing); when omitted, one is constructed lazily on
                first use.

        Raises:
            ValueError: If no entity scope (``user_id`` / ``agent_id`` / ``run_id``
                / ``app_id``) is provided.
        """
        scope = {
            "user_id": user_id,
            "agent_id": agent_id,
            "run_id": run_id,
            "app_id": app_id,
        }
        self.scope = {key: value for key, value in scope.items() if value}
        if not self.scope:
            raise ValueError("Mem0MemoryStore requires at least one of user_id, agent_id, run_id, or app_id")

        # MemoryStore Protocol attributes.
        self.name = name
        self.description = description
        self.max_search_results = max_search_results
        self.writable = writable
        self.extraction = extraction

        # Mem0-specific configuration.
        self.metadata = metadata

        self._api_key = api_key
        self._host = host
        self._config = config
        self._mem0_client = mem0_client
        self._client = client

    @property
    def client(self) -> Mem0ServiceClient:
        """The Mem0 service client, constructed lazily on first use."""
        if self._client is None:
            self._client = Mem0ServiceClient(
                api_key=self._api_key,
                host=self._host,
                config=self._config,
                client=self._mem0_client,
            )
        return self._client

    async def search(self, query: str, options: SearchOptions | None = None) -> list[MemoryEntry]:
        """Search Mem0 for entries matching ``query``, ordered by relevance."""
        top_k = options.get("max_search_results") if options is not None else None
        if top_k is None:
            top_k = self.max_search_results
        if top_k is None:
            top_k = DEFAULT_MAX_SEARCH_RESULTS

        memories = await asyncio.to_thread(self.client.search_memories, query, self.scope, top_k)
        return [self._to_entry(memory) for memory in memories]

    async def add(self, content: str, metadata: dict[str, Any] | None = None) -> Any:
        """Write a single distilled fact to Mem0 verbatim (``infer=False``).

        Extraction writes are at-least-once, so this tolerates duplicate content;
        Mem0 de-duplicates on the server.
        """
        return await asyncio.to_thread(
            self.client.store_memory,
            content,
            self.scope,
            self._merge_metadata(metadata),
        )

    async def add_messages(self, messages: list[Message], context: AddMessagesContext | None = None) -> Any:
        """Ingest raw conversation turns for Mem0 server-side extraction (``infer=True``).

        This is the sink the manager uses for extraction when no client-side
        extractor is configured, so facts are distilled by Mem0 itself.
        """
        payload = [dict(message) for message in messages]
        return await asyncio.to_thread(self.client.store_messages, payload, self.scope)

    def _merge_metadata(self, metadata: dict[str, Any] | None) -> dict[str, Any] | None:
        """Merge per-call metadata over the store's default metadata."""
        if self.metadata and metadata:
            return {**self.metadata, **metadata}
        return metadata or self.metadata

    @staticmethod
    def _to_entry(memory: dict[str, Any]) -> MemoryEntry:
        """Map a Mem0 memory dict to a Strands :class:`~strands.memory.MemoryEntry`."""
        content = memory.get("memory") or memory.get("content") or ""
        metadata: dict[str, Any] = {}
        for key in ("id", "score", "categories", "created_at", "updated_at", *_SCOPE_FIELDS):
            value = memory.get(key)
            if value is not None:
                metadata[key] = value
        extra = memory.get("metadata")
        if isinstance(extra, dict):
            metadata.update(extra)
        return MemoryEntry(content=content, metadata=metadata or None)
