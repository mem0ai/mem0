from abc import ABC, abstractmethod


class VectorStoreBase(ABC):
    @abstractmethod
    def create_col(self, name, vector_size, distance):
        """Create a new collection."""
        pass

    @abstractmethod
    def insert(self, vectors, payloads=None, ids=None):
        """Insert vectors into a collection."""
        pass

    @abstractmethod
    def search(self, query, vectors, limit=5, filters=None):
        """Search for similar vectors.

        All implementations MUST return OutputData with ``score`` as a
        **similarity** value where **higher = more similar**.  The
        recommended range is [0, 1].

        If the underlying engine returns a *distance* (lower = more
        similar), the implementation must convert before returning:

        * Cosine distance  → ``max(0.0, 1.0 - distance)``
        * L2 / Euclidean   → ``1.0 / (1.0 + distance)``
        * Inner-product / similarity → use as-is

        This contract ensures ``Memory.search(threshold=…)`` works
        consistently across all backends.
        """
        pass

    @abstractmethod
    def delete(self, vector_id):
        """Delete a vector by ID."""
        pass

    @abstractmethod
    def update(self, vector_id, vector=None, payload=None):
        """Update a vector and its payload."""
        pass

    @abstractmethod
    def get(self, vector_id):
        """Retrieve a vector by ID."""
        pass

    @abstractmethod
    def list_cols(self):
        """List all collections."""
        pass

    @abstractmethod
    def delete_col(self):
        """Delete a collection."""
        pass

    @abstractmethod
    def col_info(self):
        """Get information about a collection."""
        pass

    @abstractmethod
    def list(self, filters=None, limit=None):
        """List all memories."""
        pass

    @abstractmethod
    def reset(self):
        """Reset by delete the collection and recreate it."""
        pass
