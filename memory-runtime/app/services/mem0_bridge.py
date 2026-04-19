from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.models.memory_unit import MemoryUnit


@dataclass
class ExternalMemoryResult:
    external_id: str
    content: str
    space_type: str
    metadata: dict[str, Any]


class NullMem0Bridge:
    def search(self, *, query: str, namespace_id: str, agent_id: str | None, limit: int) -> list[ExternalMemoryResult]:
        return []

    def sync_memory(
        self,
        *,
        memory_unit: MemoryUnit,
        namespace_id: str,
        agent_id: str | None,
        space_type: str | None,
    ) -> None:
        return None


class HttpMem0Bridge:
    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float,
        api_key: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.api_key = api_key
        self.transport = transport

    def search(self, *, query: str, namespace_id: str, agent_id: str | None, limit: int) -> list[ExternalMemoryResult]:
        payload = self._scoped_payload(namespace_id=namespace_id, agent_id=agent_id)
        payload.update({"query": query, "limit": limit})

        response = self._client().post("/search", json=payload)
        response.raise_for_status()
        body = response.json()
        results = body.get("results", body if isinstance(body, list) else [])
        mapped: list[ExternalMemoryResult] = []
        for item in results:
            metadata = item.get("metadata") or {}
            mapped.append(
                ExternalMemoryResult(
                    external_id=str(item.get("id", "")),
                    content=item.get("memory", ""),
                    space_type=str(metadata.get("space_type", "project-space")),
                    metadata=metadata,
                )
            )
        return mapped

    def sync_memory(
        self,
        *,
        memory_unit: MemoryUnit,
        namespace_id: str,
        agent_id: str | None,
        space_type: str | None,
    ) -> None:
        payload = self._scoped_payload(namespace_id=namespace_id, agent_id=agent_id)
        payload.update(
            {
                "messages": [{"role": "assistant", "content": memory_unit.content}],
                "infer": False,
                "metadata": {
                    "namespace_id": namespace_id,
                    "space_type": space_type,
                    "memory_unit_id": memory_unit.id,
                    "source": "memory-runtime",
                },
            }
        )
        response = self._client().post("/memories", json=payload)
        response.raise_for_status()

    def _scoped_payload(self, *, namespace_id: str, agent_id: str | None) -> dict[str, Any]:
        if agent_id:
            return {"agent_id": agent_id}
        return {"user_id": namespace_id}

    def _client(self) -> httpx.Client:
        headers = {}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout_seconds,
            headers=headers,
            transport=self.transport,
        )


def build_mem0_bridge(settings: Settings | None = None) -> NullMem0Bridge | HttpMem0Bridge:
    settings = settings or get_settings()
    if not settings.mem0_bridge_enabled or not settings.mem0_base_url:
        return NullMem0Bridge()
    return HttpMem0Bridge(
        base_url=settings.mem0_base_url,
        timeout_seconds=settings.mem0_timeout_seconds,
        api_key=settings.mem0_api_key,
    )
