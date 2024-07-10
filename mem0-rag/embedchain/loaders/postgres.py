import hashlib
import logging
from typing import Any, Optional

from embedchain.loaders.base_loader import BaseLoader

logger = logging.getLogger(__name__)


class PostgresLoader(BaseLoader):
    def __init__(self, config: Optional[dict[str, Any]] = None):
        super().__init__()
        if not config:
            raise ValueError(f"Must provide the valid config. Received: {config}")

        self.connection = None
        self.cursor = None
        self._setup_loader(config=config)

    def _setup_loader(self, config: dict[str, Any]):
        try:
            import psycopg
        except ImportError as e:
            raise ImportError(
                "Unable to import required packages. \
                    Run `pip install --upgrade 'embedchain[postgres]'`"
            ) from e

        if "url" in config:
            config_info = config.get("url")
        else:
            conn_params = []
            for key, value in config.items():
                conn_params.append(f"{key}={value}")
            config_info = " ".join(conn_params)

        logger.info(f"Connecting to postrgres sql: {config_info}")
        self.connection = psycopg.connect(conninfo=config_info)
        self.cursor = self.connection.cursor()

    @staticmethod
    def _check_query(query):
        if not isinstance(query, str):
            raise ValueError(
                f"Invalid postgres query: {query}. Provide the valid source to add from postgres, make sure you are following `https://docs.embedchain.ai/data-sources/postgres`",  # noqa:E501
            )

    def load_data(self, query):
        self._check_query(query)
        try:
            data = []
            data_content = []
            self.cursor.execute(query)
            results = self.cursor.fetchall()
            for result in results:
                doc_content = str(result)
                data.append({"content": doc_content, "meta_data": {"url": query}})
                data_content.append(doc_content)
            doc_id = hashlib.sha256((query + ", ".join(data_content)).encode()).hexdigest()
            return {
                "doc_id": doc_id,
                "data": data,
            }
        except Exception as e:
            raise ValueError(f"Failed to load data using query={query} with: {e}")

    def close_connection(self):
        if self.cursor:
            self.cursor.close()
            self.cursor = None
        if self.connection:
            self.connection.close()
            self.connection = None
