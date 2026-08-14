from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class HistoryStoreBase(ABC):
    """Pluggable backend for memory change history and session messages."""

    @abstractmethod
    def add_history(
        self,
        memory_id: str,
        old_memory: Optional[str],
        new_memory: Optional[str],
        event: str,
        *,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
        is_deleted: int = 0,
        actor_id: Optional[str] = None,
        role: Optional[str] = None,
    ) -> None:
        """Insert a single history row."""

    @abstractmethod
    def batch_add_history(self, records: List[Dict[str, Any]]) -> None:
        """Insert multiple history rows in one transaction."""

    @abstractmethod
    def get_history(self, memory_id: str) -> List[Dict[str, Any]]:
        """Return history rows for a memory, oldest first."""

    @abstractmethod
    def save_messages(self, messages: List[Dict[str, Any]], session_scope: str) -> None:
        """Persist messages for a session and keep only the latest 10."""

    @abstractmethod
    def get_last_messages(self, session_scope: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Return the latest messages for a session, chronological order."""

    @abstractmethod
    def reset(self) -> None:
        """Drop history and messages tables. Caller should replace this instance."""

    @abstractmethod
    def close(self) -> None:
        """Release backend resources."""
