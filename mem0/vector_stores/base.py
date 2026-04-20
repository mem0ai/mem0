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
    def search(self, query, vectors, top_k=5, filters=None):
        """Search for similar vectors."""
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
    def list(self, filters=None, top_k=None):
        """List all memories."""
        pass

    @abstractmethod
    def reset(self):
        """Reset by delete the collection and recreate it."""
        pass

    def keyword_search(self, query: str, top_k: int = 5, filters: dict = None):
        """Keyword/BM25 full-text search. Returns None if not supported by this store.

        Override in subclasses that support native keyword/BM25 search.
        Returns results in the same format as search() -- list of objects with
        id, score, and payload attributes.

        Args:
            query: The search query text (should be lemmatized for best results).
            top_k: Maximum number of results to return.
            filters: Optional metadata filters (same format as search filters).

        Returns:
            List of search results with id, score, payload, or None if not supported.
        """
        return None

    def search_batch(self, queries: list, vectors_list: list, top_k: int = 1, filters: dict = None):
        """Batch search for multiple queries at once.

        Default implementation calls search() sequentially. Override in subclasses
        with native batch support (e.g., Qdrant query_batch_points).

        Args:
            queries: List of query texts.
            vectors_list: List of query vectors (one per query).
            top_k: Maximum results per query.
            filters: Optional metadata filters applied to all queries.

        Returns:
            List of result lists, one per query.
        """
        return [self.search(q, v, top_k=top_k, filters=filters) for q, v in zip(queries, vectors_list)]
