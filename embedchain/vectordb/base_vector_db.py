class BaseVectorDB:
    def __init__(self):
        self.client = self._get_or_create_db()
        self.collection = self._get_or_create_collection()

    def _get_or_create_db(self):
        raise NotImplementedError

    def _get_or_create_collection(self):
        raise NotImplementedError