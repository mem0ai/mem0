from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class MemoryBase(ABC):
    @abstractmethod
    def get(self, memory_id: str) -> Dict[str, Any]:
        """
        Retrieve a memory by ID.

        Args:
            memory_id: ID of the memory to retrieve.

        Returns:
            Retrieved memory as a dictionary.
        """
        pass

    @abstractmethod
    def get_all(self) -> List[Dict[str, Any]]:
        """
        List all memories.

        Returns:
            List of all memories.
        """
        pass

    @abstractmethod
    def update(self, memory_id: str, data: str) -> Dict[str, str]:
        """
        Update a memory by ID.

        Args:
            memory_id: ID of the memory to update.
            data: New content to update the memory with.

        Returns:
            Success message indicating the memory was updated.
        """
        pass

    @abstractmethod
    def delete(self, memory_id: str) -> None:
        """
        Delete a memory by ID.

        Args:
            memory_id: ID of the memory to delete.
        """
        pass

    @abstractmethod
    def history(self, memory_id: str) -> List[Dict[str, Any]]:
        """
        Get the history of changes for a memory by ID.

        Args:
            memory_id: ID of the memory to get history for.

        Returns:
            List of changes for the memory.
        """
        pass
