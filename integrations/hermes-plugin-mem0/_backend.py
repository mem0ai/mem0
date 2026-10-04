"""Backend abstraction for Mem0 Platform and OSS modes."""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from contextlib import closing, nullcontext, suppress
from copy import deepcopy
from dataclasses import dataclass, field
from threading import RLock
from typing import Any

logger = logging.getLogger(__name__)


def _add_kwargs(user_id: str, agent_id: str, infer: bool, metadata: dict | None) -> dict[str, Any]:
    return {"user_id": user_id, "agent_id": agent_id, "infer": infer, **({"metadata": metadata} if metadata else {})}


def _unwrap_results(response: Any) -> list:
    """Normalize API response — extract results list from dict or pass through."""
    return response.get("results", []) if isinstance(response, dict) else response if isinstance(response, list) else []


class Mem0Backend(ABC):
    """Unified interface over Platform (MemoryClient), self-hosted (HTTP) and OSS (Memory) backends.
    update()/delete() are template methods: subclasses implement raw ``_update``/``_delete``."""

    @abstractmethod
    def search(self, query: str, *, filters: dict, top_k: int = 10, rerank: bool = False) -> list[dict]: ...
    @abstractmethod
    def add(self, messages: list, *, user_id: str, agent_id: str, infer: bool = False, metadata: dict | None = None) -> dict: ...
    @abstractmethod
    def get(self, memory_id: str) -> dict | None: ...
    @abstractmethod
    def _update(self, memory_id: str, text: str) -> None: ...
    @abstractmethod
    def _delete(self, memory_id: str) -> None: ...

    def update(self, memory_id: str, text: str) -> dict:
        self._update(memory_id, text)
        return {"result": "Memory updated.", "memory_id": memory_id}

    def delete(self, memory_id: str) -> dict:
        self._delete(memory_id)
        return {"result": "Memory deleted.", "memory_id": memory_id}

    def close(self) -> None:
        pass


class PlatformBackend(Mem0Backend):
    """Wraps mem0.MemoryClient for Mem0 Platform (cloud API)."""

    def __init__(self, api_key: str):
        from mem0 import MemoryClient
        self._client = MemoryClient(api_key=api_key)

    def search(self, query: str, *, filters: dict, top_k: int = 10, rerank: bool = False) -> list[dict]:
        return _unwrap_results(self._client.search(query, filters=filters, top_k=top_k, rerank=rerank))

    def add(self, messages: list, *, user_id: str, agent_id: str, infer: bool = False, metadata: dict | None = None) -> dict:
        return self._client.add(messages, **_add_kwargs(user_id, agent_id, infer, metadata))

    def get(self, memory_id: str) -> dict | None:
        return self._client.get(memory_id)

    def _update(self, memory_id: str, text: str) -> None:
        self._client.update(memory_id=memory_id, text=text)

    def _delete(self, memory_id: str) -> None:
        self._client.delete(memory_id=memory_id)


class SelfHostedBackend(Mem0Backend):
    """Direct HTTP backend for a self-hosted Mem0 server (the FastAPI ``server/``).
    mem0.MemoryClient is hardwired to the cloud API (``Authorization: Token``, ``GET /v1/ping/`` in ``__init__``),
    so this speaks the server's real contract: ``X-API-Key`` auth and the ``/memories`` / ``/search`` routes."""

    def __init__(self, api_key: str, host: str, transport=None):
        import httpx
        headers = {"Content-Type": "application/json", **({"X-API-Key": api_key} if api_key else {})}  # key omitted only for AUTH_DISABLED servers
        # Connect-level retries keep one dropped SYN from counting toward the breaker. ``transport`` is injectable for tests.
        self._client = httpx.Client(base_url=host.rstrip("/"), headers=headers, timeout=30.0, transport=transport or httpx.HTTPTransport(retries=2))
        self._capture_timeout = httpx.Timeout(120.0, connect=30.0)

    def _json(self, method: str, path: str, **kwargs) -> Any:
        resp = self._client.request(method, path, **kwargs)
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    def search(self, query: str, *, filters: dict, top_k: int = 10, rerank: bool = False) -> list[dict]:
        # rerank is platform-only; the self-hosted /search ignores it. user_id belongs in filters (top-level is deprecated).
        return _unwrap_results(self._json("POST", "/search", json={"query": query, "top_k": top_k, **({"filters": filters} if filters else {})}))

    def add(self, messages: list, *, user_id: str, agent_id: str, infer: bool = False, metadata: dict | None = None) -> dict:
        # Server-side extraction takes longer than a search or verbatim write.
        return self._json("POST", "/memories", json={"messages": messages, **_add_kwargs(user_id, agent_id, infer, metadata)},
                          timeout=self._capture_timeout if infer else self._client.timeout)

    def get(self, memory_id: str) -> dict | None:
        return self._json("GET", f"/memories/{memory_id}")

    def _update(self, memory_id: str, text: str) -> None:
        self._json("PUT", f"/memories/{memory_id}", json={"text": text})

    def _delete(self, memory_id: str) -> None:
        self._json("DELETE", f"/memories/{memory_id}")

    def close(self) -> None:
        with suppress(Exception):
            self._client.close()


_DIRECT_OPENAI_PROVIDER = "hermes_openai"
_DIRECT_OPENAI_CLASS_PATH = f"{__package__}._openai_llm.DirectOpenAILLM"


@dataclass
class _LocalQdrantMemory:
    memory: Any
    config: dict
    profile: str
    lock: Any = field(default_factory=RLock)
    users: int = 1


_LOCAL_QDRANT_MEMORIES: dict[str, _LocalQdrantMemory] = {}
_LOCAL_QDRANT_LOCK = RLock()


def _register_direct_openai_provider() -> None:
    """Register Hermes' OpenAI-only Mem0 LLM provider once per factory."""
    from mem0.configs.llms.openai import OpenAIConfig
    from mem0.utils.factory import LlmFactory
    provider_map = getattr(LlmFactory, "provider_to_class", None)
    register_provider = getattr(LlmFactory, "register_provider", None)
    if not isinstance(provider_map, dict) or not callable(register_provider):
        raise RuntimeError("mem0 LlmFactory does not support the provider registration required for the Hermes OpenAI OSS backend")
    if provider_map.get(_DIRECT_OPENAI_PROVIDER) != (_DIRECT_OPENAI_CLASS_PATH, OpenAIConfig):
        register_provider(_DIRECT_OPENAI_PROVIDER, _DIRECT_OPENAI_CLASS_PATH, OpenAIConfig)


class OSSBackend(Mem0Backend):
    """Wraps mem0.Memory for self-hosted (OSS) mode."""

    def __init__(self, oss_config: dict):
        from ._oss_providers import EMBEDDER_PROVIDERS, KNOWN_DIMS, LLM_PROVIDERS

        self._local_path = None
        self._owner = None
        self._lock = nullcontext()
        self._closed = False

        def _provider_block(name: str, registry: dict) -> dict:
            """Copy of oss_config[name] with the legacy ``api_base`` key mapped to the provider's canonical base-URL key."""
            block = dict(oss_config[name])
            provider_config = dict(block.get("config", {}))
            legacy_base = provider_config.pop("api_base", None)
            canonical_key = registry.get(str(block.get("provider") or "").strip().lower(), {}).get("base_url_key")
            if legacy_base and canonical_key:
                provider_config.setdefault(canonical_key, legacy_base)
            if str(block.get("provider") or "").strip().lower() == "openai":
                from agent.secret_scope import get_secret

                # Resolve profile secrets before comparing configurations for sharing.
                provider_config["api_key"] = provider_config.get("api_key") or get_secret("OPENAI_API_KEY", "")
                if not provider_config["api_key"]:
                    raise ValueError(f"OpenAI API key is required for the Hermes Mem0 OSS {name}")
                provider_config["openai_base_url"] = (
                    provider_config.get("openai_base_url") or get_secret("OPENAI_API_BASE", "")
                    or get_secret("OPENAI_BASE_URL", "") or "https://api.openai.com/v1"
                )
            block["config"] = provider_config
            return block

        vector_store = dict(oss_config["vector_store"])
        vs_config = dict(vector_store.get("config", {}))
        if vs_config.get("path"):
            vs_config["path"] = os.path.expanduser(vs_config["path"])
        embedder_config = oss_config.get("embedder", {}).get("config", {})
        dims = embedder_config.get("embedding_dims") or KNOWN_DIMS.get(embedder_config.get("model", ""))
        if dims:
            vs_config["embedding_model_dims"] = dims
        remote = (vs_config.get("host") and vs_config.get("port")) or vs_config.get("url") or vs_config.get("api_key")
        if (vector_store.get("provider", "qdrant") == "qdrant" and not vs_config.get("client")
                and not remote and vs_config.get("https") is None):
            from mem0.configs.vector_stores.qdrant import QdrantConfig
            path = vs_config.get("path", QdrantConfig.model_fields["path"].default)
            if path:
                self._local_path = vs_config["path"] = os.path.realpath(os.path.expanduser(path))
        vector_store["config"] = vs_config
        config = {"vector_store": vector_store, "llm": _provider_block("llm", LLM_PROVIDERS), "embedder": _provider_block("embedder", EMBEDDER_PROVIDERS), "version": "v1.1"}
        if self._local_path:
            from hermes_constants import get_hermes_home
            profile = os.path.realpath(get_hermes_home())
            with _LOCAL_QDRANT_LOCK:
                owner = _LOCAL_QDRANT_MEMORIES.get(self._local_path)
                if owner is None:
                    owner = _LocalQdrantMemory(self._create_memory(config, dims), deepcopy(config), profile)
                    _LOCAL_QDRANT_MEMORIES[self._local_path] = owner
                else:
                    if owner.profile != profile or owner.config != config:
                        raise ValueError("Local Qdrant storage is already open with a different profile or configuration. "
                                         "Existing memories were preserved. Close its active sessions before changing settings, "
                                         "or use a separate storage path.")
                    owner.users += 1
                self._owner, self._lock, self._memory = owner, owner.lock, owner.memory
        else:
            self._memory = self._create_memory(config, dims)

    @staticmethod
    def _create_memory(config: dict, dims: int | None):
        from mem0 import Memory
        vector_store = config["vector_store"]
        vs_config = vector_store["config"]
        if dims:
            OSSBackend._reject_dimension_mismatch(vector_store.get("provider", "qdrant"), vs_config, dims)
        else:
            logger.warning("Unknown embedding dimensions; skipping dimension-change guard for collection %r.",
                           vs_config.get("collection_name", "mem0"))
        if str(config["llm"].get("provider") or "").strip().lower() == "openai":
            # mem0 validates LlmConfig.provider before its factory lookup: build the supported OpenAI config, then swap the provider.
            _register_direct_openai_provider()
            from mem0.configs.base import MemoryConfig
            memory_config = MemoryConfig(**config)
            try:
                memory_config.llm.provider = _DIRECT_OPENAI_PROVIDER
            except (AttributeError, TypeError) as exc:
                raise RuntimeError("mem0 MemoryConfig does not expose a mutable llm.provider for the Hermes OpenAI OSS backend") from exc
            return Memory(memory_config)
        return Memory.from_config(config)

    @staticmethod
    def _detect_current_dims(provider: str, vs_config: dict, collection_name: str) -> int | None:
        """Current embedding dimension of ``collection_name``, or None if it doesn't exist yet.
        Raises on any failure to connect/inspect so the caller can decide whether to skip the guard."""
        if provider == "qdrant":
            from qdrant_client import QdrantClient
            path, url, host = vs_config.get("path"), vs_config.get("url"), vs_config.get("host")
            if path:
                client = QdrantClient(path=path)
            elif url:
                client = QdrantClient(url=url, api_key=vs_config.get("api_key"))
            elif host:
                client = QdrantClient(host=host, port=vs_config.get("port") or 6333, api_key=vs_config.get("api_key"))
            else:
                return None
            with closing(client):
                if not client.collection_exists(collection_name):
                    return None
                vectors = client.get_collection(collection_name).config.params.vectors
                # Named-vector collections expose a dict; unnamed expose an object with .size.
                if isinstance(vectors, dict):
                    vectors = next(iter(vectors.values()), None)
                return getattr(vectors, "size", None)
        elif provider == "pgvector":
            import psycopg2
            conn_params = {k: vs_config[k] for k in ("host", "port", "user", "password", "dbname", "sslmode") if vs_config.get(k)}
            with closing(psycopg2.connect(**conn_params)) as conn:
                conn.autocommit = True
                with closing(conn.cursor()) as cur:
                    cur.execute("SELECT atttypmod FROM pg_attribute WHERE attrelid = %s::regclass AND attname = 'vector'", (collection_name,))
                    row = cur.fetchone()
                    return row[0] if row and row[0] > 0 else None
        return None

    @staticmethod
    def _reject_dimension_mismatch(provider: str, vs_config: dict, expected_dims: int) -> None:
        """Reject embedding dimension changes without deleting existing memories."""
        collection_name = vs_config.get("collection_name", "mem0")
        try:
            current_dims = OSSBackend._detect_current_dims(provider, vs_config, collection_name)
        except Exception as dimension_detection_error:
            logger.warning(
                "Could not determine embedding dimensions for collection %r (%s): %s. Skipping dimension-change guard.",
                collection_name, provider, dimension_detection_error,
            )
            return
        if current_dims is not None and current_dims != expected_dims:
            raise ValueError(
                f"Collection {collection_name!r} has {current_dims} embedding dimensions, but {expected_dims} are configured. "
                "Existing memories were preserved. Restore the previous embedder or use a new collection_name."
            )

    def search(self, query: str, *, filters: dict, top_k: int = 10, rerank: bool = False) -> list[dict]:
        return _unwrap_results(self._call("search", query, filters=filters, top_k=top_k))

    def add(self, messages: list, *, user_id: str, agent_id: str, infer: bool = False, metadata: dict | None = None) -> dict:
        return self._call("add", messages, **_add_kwargs(user_id, agent_id, infer, metadata))

    def get(self, memory_id: str) -> dict | None:
        return self._call("get", memory_id)

    def _update(self, memory_id: str, text: str) -> None:
        self._call("update", memory_id, data=text)

    def _delete(self, memory_id: str) -> None:
        self._call("delete", memory_id)

    def _call(self, method, *args, **kwargs):
        # ponytail: serialize whole local SDK operations, including extraction's read/modify/write.
        # Use a Qdrant server for parallel throughput or access from multiple processes.
        with self._lock:
            if self._closed:
                raise RuntimeError("Mem0 backend is closed")
            return getattr(self._memory, method)(*args, **kwargs)

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            if self._owner:
                with _LOCAL_QDRANT_LOCK:
                    self._owner.users -= 1
                    if self._owner.users == 0:
                        self._close_memory()
                        del _LOCAL_QDRANT_MEMORIES[self._local_path]
            else:
                self._close_memory()

    def _close_memory(self):
        with suppress(Exception):
            telemetry = getattr(self._memory, "telemetry", None)
            if telemetry and hasattr(telemetry, "posthog"):
                with suppress(Exception):
                    telemetry.posthog.shutdown()
        vs = getattr(self._memory, "vector_store", None)
        telemetry_vs = getattr(self._memory, "_telemetry_vector_store", None)
        resources = (self._memory, vs, getattr(vs, "client", None), getattr(telemetry_vs, "client", None))
        for obj in {id(obj): obj for obj in resources if obj is not None}.values():
            if hasattr(obj, "close"):
                with suppress(Exception):
                    obj.close()
