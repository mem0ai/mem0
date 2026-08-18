"""A thin wrapper around the Mem0 SDK used by :class:`~strands_mem0.store.Mem0MemoryStore`.

The wrapper hides the one real asymmetry in the Mem0 API: writes take the entity
scope (``user_id`` / ``agent_id`` / ``run_id`` / ``app_id``) as top-level keyword
arguments, while the hosted platform's ``search`` rejects those top-level and
requires them inside a ``filters`` dict. The store therefore always passes a plain
``scope`` mapping and lets this client route it correctly for whichever backend is
in use.

Two backends are supported, matching the ``mem0_memory`` tool in
``strands-agents-tools``:

- **Mem0 Platform** (default): the hosted ``api.mem0.ai`` service via
  :class:`mem0.MemoryClient`, authenticated with ``MEM0_API_KEY``.
- **Mem0 OSS** (self-hosted): a :class:`mem0.Memory` built from a config dict, for
  users running their own vector/graph stores.
"""

from __future__ import annotations

import os
from typing import Any

# Platform client classes route entity scope through `filters` on search; the OSS
# `Memory` takes it as top-level kwargs. We detect the platform by class name so we
# do not have to import (and thus hard-depend on) a specific mem0 submodule here.
_PLATFORM_CLIENTS = {"MemoryClient", "AsyncMemoryClient"}


def _is_platform_client(client: Any) -> bool:
    """Whether ``client`` is a hosted Mem0 platform client (vs an OSS ``Memory``)."""
    return type(client).__name__ in _PLATFORM_CLIENTS


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
        """
        if client is not None:
            self.mem0 = client
            self.is_platform = _is_platform_client(client)
            return

        if config is not None:
            try:
                from mem0 import Memory
            except ImportError as err:  # pragma: no cover - exercised via install docs
                raise ImportError(
                    "The mem0ai package is required. Install it with: pip install 'strands-mem0'"
                ) from err
            self.mem0 = Memory.from_config(config)
            self.is_platform = False
            return

        try:
            from mem0 import MemoryClient
        except ImportError as err:  # pragma: no cover - exercised via install docs
            raise ImportError("The mem0ai package is required. Install it with: pip install 'strands-mem0'") from err
        api_key = api_key or os.environ.get("MEM0_API_KEY")
        # MemoryClient(host=None) would override the SDK default with None, so only
        # pass host when the caller actually set one.
        self.mem0 = MemoryClient(api_key=api_key, host=host) if host else MemoryClient(api_key=api_key)
        self.is_platform = True

    def store_memory(
        self,
        content: str,
        scope: dict[str, str],
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        """Store one discrete fact verbatim (``infer=False``).

        Used by the store's ``add`` sink -- the content is already a distilled
        fact (from the ``add_memory`` tool or a client-side extractor), so Mem0's
        own extraction is skipped to preserve it exactly.
        """
        return self.mem0.add(content, metadata=metadata, infer=False, **scope)

    def store_messages(self, messages: list[dict[str, Any]], scope: dict[str, str]) -> Any:
        """Hand raw conversation turns to Mem0 for server-side extraction (``infer=True``).

        Used by the store's ``add_messages`` sink. Mem0 extracts and de-duplicates
        facts on the server, so no client-side model call is needed; extraction
        writes are at-least-once, which Mem0 tolerates.
        """
        return self.mem0.add(messages, infer=True, **scope)

    def search_memories(self, query: str, scope: dict[str, str], top_k: int) -> list[dict[str, Any]]:
        """Semantic recall, scoped to the store's entity.

        Routes ``scope`` through ``filters`` on the platform client and as
        top-level kwargs on the OSS ``Memory``, then normalizes the two response
        shapes to a plain list of memory dicts.
        """
        if self.is_platform:
            response = self.mem0.search(query, filters=dict(scope), top_k=top_k)
        else:
            response = self.mem0.search(query, limit=top_k, **scope)
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
