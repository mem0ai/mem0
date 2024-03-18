import logging
import os
from typing import Optional, Union, Any

try:
    import vecs
    from vecs.collections import Collection, CollectionNotFound

except ImportError:
    raise ImportError(
        "Supabase requires extra dependencies. Install with `pip install --upgrade embedchain[vecs]`"
    ) from None

from embedchain.helpers.json_serializable import register_deserializable
from embedchain.vectordb.base import BaseVectorDB
from embedchain.config.vectordb.supabase import SupabaseDBConfig

logger = logging.getLogger(__name__)


class SupabaseVectorDB(BaseVectorDB):
    """Vector database using Supabase.

    In this vector store, embeddings are stored in Postgres table using pgvector.

    During query time, the index uses pgvector/Supabase to query for the top
    k most similar nodes.

    Args:
        postgres_connection_string (str):
            postgres connection string

        collection_name (str):
            name of the collection to store the embeddings in

    """

    stores_text = True
    flat_metadata = False
    _client: Optional[Any] = None
    _collection: Optional[Collection] = None

    def __init__(
        self,
        postgres_connection_string: str,
        collection_name: str,
        dimension: int,
        config: SupabaseDBConfig = None,
        **kwargs: Any,
    ) -> None:

        self._client = vecs.create_client(postgres_connection_string)

        try:
            self._collection = self._client.get_collection(name=collection_name)
        except CollectionNotFound:
            logger.info(f"Collection {collection_name} not found." f"try creating one with dimension {dimension}")
            self._collection = self._client.create_collection(name=collection_name, dimension=dimension)

        if config is None:
            self.config = SupabaseDBConfig()
        else:
            if not isinstance(config, SupabaseDBConfig):
                raise TypeError(
                    "config is not a `SupabaseDBConfig` instance. "
                    "Please make sure the type is right and that you are passing an instance."
                )
            self.config = config
        self.config = config

    def _initialize(self):
        """
        This method is needed because `embedder` attribute needs to be set externally before it can be initialized.
        """
        if not self.embedder:
            raise ValueError(
                "Embedder not set. Please set an embedder with `_set_embedder()` function before initialization."
            )

    def _create_index(self):
        """
        Loads the Supabase index or creates it if not present.
        """
        self._collection.create_index(measure=vecs.IndexMeasure.cosine_distance, method=vecs.IndexMethod.bktree)

    def _get_or_create_db(self):
        """Created during initialization"""
        return self._client

    def _get_or_create_collection(self):
        """Get or create a named collection."""
        return self._collection

    def get(self, ids):
        """Get database embeddings by id."""

        result = self._collection.select("*").in_("id", ids).execute()
        embeddings = result.data
        return embeddings

    def add(self, records):
        """Add data to the vector database."""

        data = [{"id": record[0], "vector": record[1], "metadata": record[2]} for record in records]
        result = self._collection.upsert(record=data).execute()
        return result

    def query(self, query):
        """Query contents from the vector database based on vector similarity."""
        # Query the Supabase collection for similar vectors based on provided query
        # Implement your similarity search algorithm here
        return []

    def count(self) -> int:
        """Count the number of documents/chunks embedded in the database."""
        # Count the number of documents in the Supabase collection
        result = self._collection.select("id").execute()
        count = len(result.data)
        return count

    def delete(self, ids):
        """Delete vectors from the database."""

        result = self._collection.delete(ids=ids).execute()
        return result
