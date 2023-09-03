class BaseVectorDB:
    """Base class for vector database."""

    def __init__(self):
        self.client = self._get_or_create_db()

    def _get_or_create_db(self):
        """Get or create the database."""
        raise NotImplementedError

    def _get_or_create_collection(self):
        raise NotImplementedError

    def get(self):
        raise NotImplementedError

    def add(self):
        raise NotImplementedError

    def query(self):
        raise NotImplementedError

    def count(self):
        raise NotImplementedError

    def reset(self):
        raise NotImplementedError
