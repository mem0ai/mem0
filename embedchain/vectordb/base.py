from embedchain.config.vectordb.base import BaseVectorDbConfig
from embedchain.embedder.base import BaseEmbedder
from embedchain.helpers.json_serializable import JSONSerializable


class BaseVectorDB(JSONSerializable):
    """Base class for vector database."""

    def __init__(self, config: BaseVectorDbConfig):
        """Initialize the database. Save the config and client as an attribute.

        :param config: Database configuration class instance.
        :type config: BaseVectorDbConfig
        """
        self.client = self._get_or_create_db()
        self.config: BaseVectorDbConfig = config

    def _initialize(self):
        """
        This method is needed because `embedder` attribute needs to be set externally before it can be initialized.

        So it's can't be done in __init__ in one step.
        """
        raise NotImplementedError

    def _get_or_create_db(self):
        """Get or create the database."""
        raise NotImplementedError

    def _get_or_create_collection(self):
        """Get or create a named collection."""
        raise NotImplementedError

    def _set_embedder(self, embedder: BaseEmbedder):
        """
        The database needs to access the embedder sometimes, with this method you can persistently set it.

        :param embedder: Embedder to be set as the embedder for this database.
        :type embedder: BaseEmbedder
        """
        self.embedder = embedder

    def get(self):
        """Get database embeddings by id."""
        raise NotImplementedError

    def add(self):
        """Add to database"""
        raise NotImplementedError

    def query(self):
        """Query contents from vector database based on vector similarity"""
        raise NotImplementedError

    def count(self) -> int:
        """
        Count number of documents/chunks embedded in the database.

        :return: number of documents
        :rtype: int
        """
        raise NotImplementedError

    def reset(self):
        """
        Resets the database. Deletes all embeddings irreversibly.
        """
        raise NotImplementedError

    def set_collection_name(self, name: str):
        """
        Set the name of the collection. A collection is an isolated space for vectors.

        :param name: Name of the collection.
        :type name: str
        """
        raise NotImplementedError

    def delete(self):
        """Delete from database."""

        raise NotImplementedError
