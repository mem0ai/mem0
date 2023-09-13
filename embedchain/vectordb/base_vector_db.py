from embedchain.config.vectordbs.BaseVectorDbConfig import BaseVectorDbConfig
from embedchain.embedder.base_embedder import BaseEmbedder
from embedchain.helper_classes.json_serializable import JSONSerializable


class BaseVectorDB(JSONSerializable):
    """Base class for vector database."""

    def __init__(self, config: BaseVectorDbConfig):
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
        raise NotImplementedError

    def _set_embedder(self, embedder: BaseEmbedder):
        self.embedder = embedder

    def get(self):
        raise NotImplementedError

    def add(self):
        raise NotImplementedError

    def query(self):
        raise NotImplementedError

    def count(self):
        raise NotImplementedError

    def delete(self):
        raise NotImplementedError

    def reset(self):
        raise NotImplementedError

    def set_collection_name(self, name: str):
        raise NotImplementedError
