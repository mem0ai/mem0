"""A thin wrapper around the Mem0 SDK used by :class:`~mem0_strands.store.Mem0MemoryStore`.

Both Mem0 backends -- the hosted platform (:class:`mem0.MemoryClient`) and
self-hosted OSS (:class:`mem0.Memory`) -- expose the same call shape to the store:

- **search** takes the entity scope inside a ``filters`` dict plus ``top_k``.
- **add** takes the entity scope as top-level keyword arguments.

The wrapper hides the two remaining differences:

- ``app_id`` is a platform-only scope; OSS ``Memory.add`` has no ``app_id``
  parameter, so it is rejected up front for the OSS backend rather than surfacing
  as a ``TypeError`` mid-call.
- the telemetry ``source`` tag is attached to platform writes only (OSS
  ``Memory.add`` has a fixed signature and would reject an unknown kwarg).
"""

from __future__ import annotations

import inspect
import os
from typing import Any

# Only the synchronous platform client is supported. ``AsyncMemoryClient``'s
# ``add`` / ``search`` are coroutine functions, so ``asyncio.to_thread`` would hand
# back an un-awaited coroutine and every write would silently no-op; it is rejected
# in ``__init__`` rather than listed here.
_PLATFORM_CLIENTS = {"MemoryClient"}

# Tags platform writes so Mem0's backend attributes the memory to this integration
# in telemetry (recognized values live in the backend's KNOWN_EVENT_SOURCES
# allowlist; unknown ones bucket into "OTHERS"). Platform only.
_SOURCE = "STRANDS"


def _is_platform_client(client: Any) -> bool:
    """Whether ``client`` is a hosted Mem0 platform client (vs an OSS ``Memory``)."""
    return type(client).__name__ in _PLATFORM_CLIENTS


def _is_async_client(client: Any) -> bool:
    """Whether ``client``'s ``add`` / ``search`` are coroutine functions."""
    return inspect.iscoroutinefunction(getattr(client, "add", None)) or inspect.iscoroutinefunction(
        getattr(client, "search", None)
    )


class Mem0ServiceClient:
    """Thin wrapper around the Mem0 SDK for the memory store.

    Exactly one backend is selected at construction time:

    - ``client`` given: use it as-is (a :class:`mem0.MemoryClient` or
      :class:`mem0.Memory`); mainly for testing and advanced/OSS setups.
    - ``config`` given: build a self-hosted :class:`mem0.Memory` from it.
    - otherwise: build a hosted :class:`mem0.MemoryClient` from ``api_key`` /
      ``$MEM0_API_KEY`` (and optional ``host``).
    """

    def __init__(
        self,
        api_key: str | None = None,
        host: str | None = None,
        config: dict[str, Any] | None = None,
        client: Any | None = None,
    ) -> None:
        """Initialize the Mem0 client.

        Args:
            api_key: Mem0 platform API key. Falls back to ``$MEM0_API_KEY``.
            host: Mem0 platform base URL. Defaults to the SDK default
                (``https://api.mem0.ai``).
            config: A Mem0 OSS config dict; when given, a self-hosted
                :class:`mem0.Memory` is built instead of the platform client.
            client: A pre-built Mem0 client to use directly (platform or OSS).

        Raises:
            ValueError: If ``client`` is an async Mem0 client (its coroutines
                would never be awaited off the worker thread).
        """
        if client is not None:
            if _is_async_client(client):
                raise ValueError(
                    "Async Mem0 clients are not supported. Pass a synchronous "
                    "mem0.MemoryClient (or a mem0.Memory / config): the store runs the "
                    "SDK in a worker thread, so an async client's coroutines would "
                    "never be awaited and every write would silently no-op."
                )
            self.mem0 = client
            self.is_platform = _is_platform_client(client)
            return

        if config is not None:
            try:
                from mem0 import Memory
            except ImportError as err:  # pragma: no cover - exercised via install docs
                raise ImportError(
                    "The mem0ai package is required. Install it with: pip install 'mem0-strands'"
                ) from err
            self.mem0 = Memory.from_config(config)
            self.is_platform = False
            return

        try:
            from mem0 import MemoryClient
        except ImportError as err:  # pragma: no cover - exercised via install docs
            raise ImportError("The mem0ai package is required. Install it with: pip install 'mem0-strands'") from err
        api_key = api_key or os.environ.get("MEM0_API_KEY")
        # MemoryClient(host=None) would override the SDK default with None, so only
        # pass host when the caller actually set one.
        self.mem0 = MemoryClient(api_key=api_key, host=host) if host else MemoryClient(api_key=api_key)
        self.is_platform = True

    def _check_scope(self, scope: dict[str, str]) -> None:
        """Reject scope the selected backend cannot honor.

        ``app_id`` exists only on the platform; the OSS ``Memory`` API has no
        ``app_id`` parameter, so we fail loudly here rather than let it surface as
        a ``TypeError`` on ``add`` or silently miss on ``search``.
        """
        if not self.is_platform and "app_id" in scope:
            raise ValueError(
                "app_id is a Mem0 platform-only scope. The OSS backend supports "
                "user_id, agent_id, and run_id; drop app_id or use the platform client."
            )

    def _write_extras(self) -> dict[str, str]:
        """Extra kwargs attached to platform writes: the telemetry ``source`` tag."""
        return {"source": _SOURCE} if self.is_platform else {}

    def store_memory(
        self,
        content: str,
        scope: dict[str, str],
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        """Store one discrete fact verbatim (``infer=False``).

        Used by the store's ``add`` sink -- the content is already a distilled fact
        (from the ``add_memory`` tool or a client-side extractor), so Mem0's own
        extraction is skipped to preserve it exactly.
        """
        self._check_scope(scope)
        return self.mem0.add(content, metadata=metadata, infer=False, **self._write_extras(), **scope)

    def store_messages(self, messages: list[dict[str, Any]], scope: dict[str, str]) -> Any:
        """Hand rendered conversation turns to Mem0 for server-side extraction (``infer=True``).

        Used by the store's ``add_messages`` sink. Mem0 extracts and de-duplicates
        facts on the server, so no client-side model call is needed.
        """
        self._check_scope(scope)
        return self.mem0.add(messages, infer=True, **self._write_extras(), **scope)

    def search_memories(self, query: str, scope: dict[str, str], top_k: int) -> list[dict[str, Any]]:
        """Semantic recall scoped to the store's entity.

        Both backends take the scope inside ``filters`` and honor ``top_k``; the
        response is normalized to a plain list of memory dicts.
        """
        self._check_scope(scope)
        response = self.mem0.search(query, filters=dict(scope), top_k=top_k)
        return _extract_results(response)


def _extract_results(response: Any) -> list[dict[str, Any]]:
    """Normalize a Mem0 search response to a list of memory dicts.

    Mem0 returns ``{"results": [...]}`` (v1.1) or, on older paths, a bare list.
    """
    if isinstance(response, dict):
        results = response.get("results", [])
        return list(results) if isinstance(results, list) else []
    if isinstance(response, list):
        return response
    return []
