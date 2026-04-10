from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union


class VectorStoreBase(ABC):
    @abstractmethod
    def create_col(self, name: str, vector_size: int, distance: str) -> None:
        """Create a new collection.

        Args:
            name: Name of the collection to create.
            vector_size: Dimensionality of the vectors to be stored.
            distance: Distance metric to use (e.g., "cosine", "euclidean").
        """
        pass

    @abstractmethod
    def insert(
        self,
        vectors: List[List[float]],
        payloads: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[Union[str, int]]] = None,
    ) -> None:
        """Insert vectors into a collection.

        Args:
            vectors: List of embedding vectors to insert.
            payloads: Optional metadata payloads associated with each vector.
            ids: Optional identifiers for each vector.
        """
        pass

    @abstractmethod
    def search(
        self,
        query: str,
        vectors: List[float],
        limit: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Search for similar vectors.

        Args:
            query: The query string.
            vectors: The query embedding vector.
            limit: Maximum number of results to return.
            filters: Optional filters to apply to the search.

        Returns:
            List of search results with scores and payloads.
        """
        pass

    @abstractmethod
    def delete(self, vector_id: Union[str, int]) -> None:
        """Delete a vector by ID.

        Args:
            vector_id: The identifier of the vector to delete.
        """
        pass

    @abstractmethod
    def update(
        self,
        vector_id: Union[str, int],
        vector: Optional[List[float]] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update a vector and its payload.

        Args:
            vector_id: The identifier of the vector to update.
            vector: Optional new embedding vector.
            payload: Optional new metadata payload.
        """
        pass

    @abstractmethod
    def get(self, vector_id: Union[str, int]) -> Optional[Dict[str, Any]]:
        """Retrieve a vector by ID.

        Args:
            vector_id: The identifier of the vector to retrieve.

        Returns:
            Dictionary containing the vector data and payload, or None if not found.
        """
        pass

    @abstractmethod
    def list_cols(self) -> List[str]:
        """List all collections.

        Returns:
            List of collection names.
        """
        pass

    @abstractmethod
    def delete_col(self) -> None:
        """Delete a collection."""
        pass

    @abstractmethod
    def col_info(self) -> Dict[str, Any]:
        """Get information about a collection.

        Returns:
            Dictionary containing collection metadata such as vector count and configuration.
        """
        pass

    @abstractmethod
    def list(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """List all memories.

        Args:
            filters: Optional filters to narrow results.
            limit: Optional maximum number of results.

        Returns:
            List of stored memory entries.
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset by deleting the collection and recreating it."""
        pass
