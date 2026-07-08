"""Abstract backend interface and factory."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from mem0_cli.config import Mem0Config


class Backend(ABC):
    """Abstract interface for mem0 backends."""

    @abstractmethod
    def add(
        self,
        content: str | None = None,
        messages: list[dict] | None = None,
        *,
        user_id: str | None = None,
        agent_id: str | None = None,
        app_id: str | None = None,
        run_id: str | None = None,
        metadata: dict | None = None,
        immutable: bool = False,
        infer: bool = True,
        expires: str | None = None,
        categories: list[str] | None = None,
    ) -> dict: ...

    @abstractmethod
    def search(
        self,
        query: str,
        *,
        user_id: str | None = None,
        agent_id: str | None = None,
        app_id: str | None = None,
        run_id: str | None = None,
        top_k: int = 10,
        threshold: float = 0.3,
        rerank: bool = False,
        keyword: bool = False,
        filters: dict | None = None,
        fields: list[str] | None = None,
    ) -> list[dict]: ...

    @abstractmethod
    def get(self, memory_id: str) -> dict: ...

    @abstractmethod
    def list_memories(
        self,
        *,
        user_id: str | None = None,
        agent_id: str | None = None,
        app_id: str | None = None,
        run_id: str | None = None,
        page: int = 1,
        page_size: int = 100,
        category: str | None = None,
        after: str | None = None,
        before: str | None = None,
    ) -> list[dict]: ...

    @abstractmethod
    def update(
        self, memory_id: str, content: str | None = None, metadata: dict | None = None
    ) -> dict: ...

    @abstractmethod
    def delete(
        self,
        memory_id: str | None = None,
        *,
        all: bool = False,
        user_id: str | None = None,
        agent_id: str | None = None,
        app_id: str | None = None,
        run_id: str | None = None,
    ) -> dict: ...

    @abstractmethod
    def delete_entities(
        self,
        *,
        user_id: str | None = None,
        agent_id: str | None = None,
        app_id: str | None = None,
        run_id: str | None = None,
    ) -> dict: ...

    @abstractmethod
    def status(
        self,
        *,
        user_id: str | None = None,
        agent_id: str | None = None,
    ) -> dict[str, Any]: ...

    @abstractmethod
    def entities(self, entity_type: str) -> list[dict]: ...

    @abstractmethod
    def list_events(self) -> list[dict]: ...

    @abstractmethod
    def get_event(self, event_id: str) -> dict: ...


def get_backend(config: Mem0Config) -> Backend:
    """Return the Platform backend."""
    from mem0_cli.backend.platform import PlatformBackend

    return PlatformBackend(config.platform)
