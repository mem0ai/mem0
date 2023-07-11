class BaseVectorDB:
    """Base class for vector database."""

    def __init__(self):
        self.client = self._get_or_create_db()
        self.collection = self._get_or_create_collection()

    def _get_or_create_db(self):
        """Get or create the database."""
        raise NotImplementedError

    def _get_or_create_collection(self):
        raise NotImplementedError
