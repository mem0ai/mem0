import logging

from embedchain.config import OceanBaseConfig
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.vectordb.base import BaseVectorDB

try:
    from pyobvector import ObVecClient
except ImportError:
    raise ImportError(
        "OceanBase requires extra dependencies. Install with `pip install --upgrade pyobvector`"
    ) from None

logger = logging.getLogger(__name__)

@register_deserializable
class OceanBaseVectorDB(BaseVectorDB):
    """`OceanBase` vector store.


    """
    def __init__(self, config: OceanBaseConfig = None):
        if config is None:
            self.config = OceanBaseConfig()
        else:
            self.config = config

        self.client = ObVecClient(
            uri=(
                self.config.host + ":" + self.config.port
            ),
            user=self.config.user,
            password=self.config.passwd,
            db_name=self.config.dbname,
        )

        super().__init__(config=self.config)

    def _initialize(self):
        """
        This method is needed because `embedder` attribute needs to be set externally before it can be initialized.

        So it's can't be done in __init__ in one step.
        """
        return super()._initialize()