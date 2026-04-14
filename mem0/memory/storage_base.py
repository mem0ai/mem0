from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class HistoryStoreBase(ABC):
    """Abstract base class for history storage backends.

    All history store implementations must implement these methods.
    The interface matches the original SQLiteManager for backward compatibility.
    """

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
        """Record a history event for a memory."""
        ...

    @abstractmethod
    def get_history(self, memory_id: str) -> List[Dict[str, Any]]:
        """Retrieve all history records for a given memory_id, ordered by created_at ascending."""
        ...

    @abstractmethod
    def reset(self) -> None:
        """Drop and recreate the history store."""
        ...

    @abstractmethod
    def close(self) -> None:
        """Release resources held by this history store."""
        ...
