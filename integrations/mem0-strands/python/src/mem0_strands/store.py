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
- :meth:`add_messages` renders raw conversation turns to text and hands them to
  Mem0 for **server-side extraction** (``infer=True``). Because this sink exists,
  enabling ``extraction`` routes messages straight to Mem0's own extraction
  pipeline -- no extra client-side model call, and Mem0's de-duplication applies.

Example:
    ```python
    from strands import Agent
    from strands.memory import MemoryManager
    from mem0_strands import Mem0MemoryStore

    # Recall + write, with Mem0 extracting facts from the conversation server-side.
    store = Mem0MemoryStore(user_id="alex", writable=True, extraction=True)
    agent = Agent(memory_manager=MemoryManager(stores=[store]))
    ```

Configure the hosted platform via the ``api_key`` argument or the ``MEM0_API_KEY``
environment variable, or pass a Mem0 OSS ``config`` dict for a self-hosted backend.
``app_id`` scope is platform-only.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from strands.memory import AddMessagesContext, MemoryEntry, MemoryStore, SearchOptions
from strands.types.content import Message

from mem0_strands import telemetry
from mem0_strands.client import Mem0ServiceClient

DEFAULT_MAX_SEARCH_RESULTS = 5
# Entity fields that scope a memory in Mem0. At least one must be set.
_SCOPE_FIELDS = ("user_id", "agent_id", "run_id", "app_id")


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
            client: A pre-built :class:`~mem0_strands.client.Mem0ServiceClient`
                (for testing, or to wrap your own raw Mem0 client via
                ``Mem0ServiceClient(client=...)``); when omitted, one is
                constructed lazily on first use from ``api_key`` / ``config``.

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
        # app_id is platform-only. When a self-hosted OSS backend is requested via
        # `config`, fail at construction rather than as a TypeError on the first
        # write (OSS Memory.add has no app_id). The injected-client OSS case is
        # caught in Mem0ServiceClient, which is the only place that knows the backend.
        if "app_id" in self.scope and config is not None:
            raise ValueError(
                "app_id is a Mem0 platform-only scope and cannot be used with a self-hosted "
                "config (OSS Memory has no app_id). Drop app_id or use the platform backend."
            )

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
        self._client = client
        self._recorded_init = False

    @property
    def client(self) -> Mem0ServiceClient:
        """The Mem0 service client, constructed lazily on first use.

        Note: constructing the underlying SDK client can block (the platform client
        validates the API key over HTTP; the OSS client builds embedders / vector
        stores), so first use is deferred and always happens inside a worker thread
        via :func:`asyncio.to_thread`, never on the event loop.
        """
        client_injected = self._client is not None
        if self._client is None:
            self._client = Mem0ServiceClient(api_key=self._api_key, host=self._host, config=self._config)
        if not self._recorded_init:
            self._recorded_init = True
            telemetry.record(
                "store.init",
                self._client,
                scopes=sorted(self.scope),
                writable=self.writable,
                extraction_enabled=bool(self.extraction),
                has_default_metadata=bool(self.metadata),
                max_search_results=self.max_search_results,
                host_overridden=bool(self._host),
                client_injected=client_injected,
            )
        return self._client

    async def search(self, query: str, options: SearchOptions | None = None) -> list[MemoryEntry]:
        """Search Mem0 for entries matching ``query``, ordered by relevance."""
        top_k = options.get("max_search_results") if options is not None else None
        if top_k is None:
            top_k = self.max_search_results
        if top_k is None:
            top_k = DEFAULT_MAX_SEARCH_RESULTS

        # ``self.client`` is resolved inside the thread so lazy construction (a
        # blocking call) does not run on the event loop.
        started = time.perf_counter()
        try:
            memories = await asyncio.to_thread(lambda: self.client.search_memories(query, self.scope, top_k))
        except Exception as exc:
            self._record("store.search", started, False, top_k=top_k, error_kind=telemetry.error_kind(exc))
            raise
        self._record("store.search", started, True, top_k=top_k, result_count=len(memories))
        return [self._to_entry(memory) for memory in memories]

    async def add(self, content: str, metadata: dict[str, Any] | None = None) -> Any:
        """Write a single distilled fact to Mem0 verbatim (``infer=False``).

        Extraction writes are at-least-once, so this tolerates duplicate content;
        Mem0 de-duplicates on the server.
        """
        merged = self._merge_metadata(metadata)
        started = time.perf_counter()
        try:
            result = await asyncio.to_thread(lambda: self.client.store_memory(content, self.scope, merged))
        except Exception as exc:
            self._record("store.add", started, False, error_kind=telemetry.error_kind(exc))
            raise
        self._record("store.add", started, True, content_chars=len(content), has_metadata=bool(merged))
        return result

    async def add_messages(self, messages: list[Message], context: AddMessagesContext | None = None) -> Any:
        """Ingest raw conversation turns for Mem0 server-side extraction (``infer=True``).

        A Strands ``Message.content`` is a list of content blocks (a text block is
        ``{"text": "..."}``); Mem0 keeps only ``{"type": "text"}`` parts, so the raw
        blocks would be dropped. We render each turn's text blocks to a string and
        skip turns that render empty (a pure tool-use / tool-result turn), so nothing
        silently no-ops.
        """
        payload: list[dict[str, str]] = []
        for message in messages:
            text = self._render_content(message.get("content"))
            if text:
                payload.append({"role": message["role"], "content": text})
        if not payload:
            return None
        started = time.perf_counter()
        try:
            result = await asyncio.to_thread(lambda: self.client.store_messages(payload, self.scope))
        except Exception as exc:
            self._record("store.add_messages", started, False, error_kind=telemetry.error_kind(exc))
            raise
        self._record(
            "store.add_messages",
            started,
            True,
            message_count=len(messages),
            rendered_count=len(payload),
            total_chars=sum(len(turn["content"]) for turn in payload),
        )
        return result

    def _record(self, event: str, started: float, success: bool, **properties: Any) -> None:
        """Send one store telemetry event, timed from ``started``."""
        if self._client is None:
            return
        telemetry.record(
            event,
            self._client,
            success=success,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            **properties,
        )

    @staticmethod
    def _render_content(content: Any) -> str:
        """Flatten a Strands message ``content`` to plain text.

        Accepts either a string or a list of content blocks; joins the text of
        every ``{"text": ...}`` block and ignores tool-use / image / other blocks.
        """
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "\n".join(part["text"] for part in content if isinstance(part, dict) and part.get("text"))
        return ""

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
