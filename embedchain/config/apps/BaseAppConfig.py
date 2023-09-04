import logging
from typing import Optional

from embedchain.config.BaseConfig import BaseConfig
from embedchain.helper_classes.json_serializable import JSONSerializable
from embedchain.vectordb.base_vector_db import BaseVectorDB


class BaseAppConfig(BaseConfig, JSONSerializable):
    """
    Parent config to initialize an instance of `App`, `OpenSourceApp` or `CustomApp`.
    """

    def __init__(
        self,
        log_level=None,
        db: Optional[BaseVectorDB] = None,
        id=None,
        collect_metrics: bool = True,
        collection_name: Optional[str] = None,
    ):
        """
        :param log_level: Optional. (String) Debug level
        ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'].
        :param db: Optional. (Vector) database instance to use for embeddings. Deprecated in favor of app(..., db).
        :param id: Optional. ID of the app. Document metadata will have this id.
        :param collect_metrics: Defaults to True. Send anonymous telemetry to improve embedchain.
        :param db_type: Optional. Initializes a default vector database of the given type.
        Using the `db` argument is preferred.
        :param es_config: Optional. elasticsearch database config to be used for connection
        :param collection_name: Optional. Default collection name.
        It's recommended to use app.set_collection_name() instead.
        """
        self._setup_logging(log_level)
        self.id = id
        self.collect_metrics = True if (collect_metrics is True or collect_metrics is None) else False
        self.collection_name = collection_name

        if db:
            self._db = db
            logging.warning(
                "DEPRECATION WARNING: Please supply the database as the second parameter during app init. "
                "Such as `app(config=config, db=db)`."
            )

        if collection_name:
            logging.warning("DEPRECATION WARNING: Please supply the collection name to the database config.")
        return

    def _setup_logging(self, debug_level):
        level = logging.WARNING  # Default level
        if debug_level is not None:
            level = getattr(logging, debug_level.upper(), None)
            if not isinstance(level, int):
                raise ValueError(f"Invalid log level: {debug_level}")

        logging.basicConfig(format="%(asctime)s [%(name)s] [%(levelname)s] %(message)s", level=level)
        self.logger = logging.getLogger(__name__)
        return
