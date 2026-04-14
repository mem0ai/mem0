from typing import Any, Dict, List, Optional

from mem0.memory.storage_base import HistoryStoreBase


class NoopHistoryStore(HistoryStoreBase):
    """A no-op history store that discards all writes and returns empty results.

    Use this when history tracking is not needed (e.g. ``disable_history=True``).
    """

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
        pass

    def get_history(self, memory_id: str) -> List[Dict[str, Any]]:
        return []

    def reset(self) -> None:
        pass

    def close(self) -> None:
        pass
