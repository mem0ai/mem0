import hashlib
import logging
from typing import Any, Optional

from embedchain.loaders.base_loader import BaseLoader
from embedchain.utils.misc import clean_string

logger = logging.getLogger(__name__)


class MySQLLoader(BaseLoader):
    def __init__(self, config: Optional[dict[str, Any]]):
        super().__init__()
        if not config:
            raise ValueError(
                f"Invalid sql config: {config}.",
                "Provide the correct config, refer `https://docs.embedchain.ai/data-sources/mysql`.",
            )

        self.config = config
        self.connection = None
        self.cursor = None
        self._setup_loader(config=config)

    def _setup_loader(self, config: dict[str, Any]):
        try:
            import mysql.connector as sqlconnector
        except ImportError as e:
            raise ImportError(
                "Unable to import required packages for MySQL loader. Run `pip install --upgrade 'embedchain[mysql]'`."  # noqa: E501
            ) from e

        try:
            self.connection = sqlconnector.connection.MySQLConnection(**config)
            self.cursor = self.connection.cursor()
        except (sqlconnector.Error, IOError) as err:
            logger.info(f"Connection failed: {err}")
            raise ValueError(
                f"Unable to connect with the given config: {config}.",
                "Please provide the correct configuration to load data from you MySQL DB. \
                    Refer `https://docs.embedchain.ai/data-sources/mysql`.",
            )

    @staticmethod
    def _check_query(query):
        if not isinstance(query, str):
            raise ValueError(
                f"Invalid mysql query: {query}",
                "Provide the valid query to add from mysql, \
                    make sure you are following `https://docs.embedchain.ai/data-sources/mysql`",
            )

    def load_data(self, query):
        self._check_query(query=query)
        data = []
        data_content = []
        self.cursor.execute(query)
        rows = self.cursor.fetchall()
        for row in rows:
            doc_content = clean_string(str(row))
            data.append({"content": doc_content, "meta_data": {"url": query}})
            data_content.append(doc_content)
        doc_id = hashlib.sha256((query + ", ".join(data_content)).encode()).hexdigest()
        return {
            "doc_id": doc_id,
            "data": data,
        }
