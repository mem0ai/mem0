from abc import ABC, abstractmethod
from typing import Dict, List, Union
import logging

logger = logging.getLogger(__name__)

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
    def list(self, filters=None, limit=None):
        """List all memories."""
        pass

    @abstractmethod
    def reset(self):
        """Reset by delete the collection and recreate it."""
        pass

    def update_metadata(self, vector_id: Union[str, int], payload: Dict) -> None:
        """
        Update only metadata without changing the vector.
        
        This is a convenience method that fetches the existing vector
        and calls update() with it. Subclasses can override this if their
        vector store has a more efficient metadata-only update API.
        
        Args:
            vector_id: ID of the vector to update
            payload: New metadata to set
        """
        try:
            # Fetch existing vector values
            vector = self._fetch_vector_values(vector_id)
            # Update with existing vector and new metadata
            self.update(vector_id=vector_id, vector=vector, payload=payload)
        except Exception as e:
            logger.error(f"Error updating metadata for vector {vector_id}: {e}")
            raise

    def _fetch_vector_values(self, vector_id: Union[str, int]) -> List[float]:
        """
        Fetch vector values for a given ID.
        
        Subclasses must implement this method to retrieve the actual
        vector values from their specific vector store.
        
        Args:
            vector_id: ID of the vector to fetch
            
        Returns:
            List[float]: The vector values
            
        Raises:
            NotImplementedError: If not implemented by subclass
            ValueError: If vector not found
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement _fetch_vector_values() "
            "to support metadata-only updates"
        )

    