import logging
from typing import Dict, List, Optional

from pydantic import BaseModel

try:
    import deeplake
except ImportError:
    raise ImportError("The 'deeplake' library is required. Please install it using 'pip install deeplake'.")

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)

class DeepLake(VectorStoreBase):
    def __init__(
        self,
        url: str,
        embedding_model_dims: int,
        quantize: bool = False,
        creds: Optional[Dict] = None,
        token: Optional[str] = None,
    ):
        """
        Initialize the DeepLake vector store.

        Args:
            url (str): The URL of the DeepLake database.
            creds (Dict, optional): Credentials for the DeepLake database.
            token (str, optional): Token for the DeepLake database.
        """
        exists = deeplake.exists(url, creds=creds, token=token)

        self.url = url
        self.creds = creds
        self.token = token
        self.embedding_model_dims = embedding_model_dims
        self.quantize = quantize

        self.client = None
        
        self.create_col(embedding_model_dims)
    
    def _collection_exists(self) -> bool:
        return deeplake.exists(self.url, creds=self.creds, token=self.token)

    def create_col(self, vector_size: int, distance: str = "cosine"):
        exists = self._collection_exists()
        if exists:
            logger.debug(f"Collection {self.url} already exists. Skipping creation.")
            self.client = deeplake.open(self.url, creds=self.creds, token=self.token)
            return
        
        schema = deeplake.schemas.TextEmbedding(embedding_size=self.embedding_model_dims, quantize=self.quantize)
        
        self.client = deeplake.create(self.url, creds=self.creds, token=self.token)







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
