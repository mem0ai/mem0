from typing import Optional

from dotenv import load_dotenv

from embedchain.helper.json_serializable import register_deserializable
from embedchain.vectordb.base import BaseVectorDB

from .base_app_config import BaseAppConfig

load_dotenv()


@register_deserializable
class CustomAppConfig(BaseAppConfig):
    """
    Config to initialize an embedchain custom `App` instance, with extra config options.
    """

    def __init__(
        self,
        log_level: str = "WARNING",
        db: Optional[BaseVectorDB] = None,
        id: Optional[str] = None,
        collect_metrics: Optional[bool] = None,
        collection_name: Optional[str] = None,
    ):
        """
        Initializes a configuration class instance for an Custom App.
        Most of the configuration is done in the `CustomApp` class itself.

        :param log_level: Debug level ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], defaults to "WARNING"
        :type log_level: str, optional
        :param db: A database class. It is recommended to set this directly in the `CustomApp` class, not this config,
        defaults to None
        :type db: Optional[BaseVectorDB], optional
        :param id: ID of the app. Document metadata will have this id., defaults to None
        :type id: Optional[str], optional
        :param collect_metrics: Send anonymous telemetry to improve embedchain, defaults to True
        :type collect_metrics: Optional[bool], optional
        :param collection_name: Default collection name. It's recommended to use app.db.set_collection_name() instead,
        defaults to None
        :type collection_name: Optional[str], optional
        """
        super().__init__(
            log_level=log_level, db=db, id=id, collect_metrics=collect_metrics, collection_name=collection_name
        )
