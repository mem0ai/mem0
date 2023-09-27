import logging
from typing import Any, Dict, List, Optional, Set

try:
    from lancedb import lancedb
    from lancedb import connect, create_table, delete, open_table
except ImportError:
    raise ImportError(
        "LanceDb requirese extra dependencies. Install with `pip install --upgrade embedchain[lancedb]`"
            ) from None

from embedchain.config import LanceDBConfig
from embedchain.helper.json_serializable import register_deserializable
from embedchain.vectordb.base import BaseVectorDB


@register_deserializable
class LanceDb(BaseVectorDB):
    """
    LanceDB as vector database
    """

    def __init__(
        self,
        config: Optional[LanceDBConfig] = None,
        ld_config: Optional[LanceDBConfig] = None,  #Backwards compatibility
    ):
        """Initialize a new LanceDB connection

        :param config: LanceDB database config, defaults to None
        :type config: LanceDBConfig, optional
        :param ld_config: `ld_config` is supported as an alias for `config` (for backwards compatibility),
         defaults to None
        :type ld_config: ElasticsearchDBConfig, optional
        :raises ValueError: No config provided
        """
        if config is None and ld_config is None:
            self.config = LanceDBConfig()
        else:
            if not isinstance(config, LanceDBConfig):
                raise TypeError(
                    "Config is not a `lancedbconfig` instance. "
                    "Please make sure the type is right and that you are passing an instance. "
                )
            self.config = config or ld_config
        self.connection = LanceDb(self.config.LD_URI, **self.config.LD_EXTRA_PARAMS)

        #call parent init here because embedder is needed
        super().__init__(config=self.config)

    def _initialize(self):
        """
        this method is needed because 'embedder' attribute needs to be externally set
        """
        if not self.embedder:
            raise ValueError("Embedder not set")
        self._get_or_create_table(self.table_name)

    def add(self, documents: List[str]) -> Any:
        """
        Add vectors to lancedb database

        :param documents: Documents
        :type documents: List[str]
        """
        if self.table_name in self.connection.table_names():
            tbl = self.connection.open_table(self.table_name)
            tbl.add(documents)
        else:
            self.connection.create_table(self.table_name, documents)

    def delete(self, where) -> None:
        """ Delete the table """
        return self.connection.delete(where=where)


    def _get_or_create_db(self):
        """called during initalization"""
        return self.connection

    def _get_or_create_table(self, name: str) -> table:
        """
        get or create a named table

        :param name: Name of the table
        :type name: str

        :return: created table
        :rtype: table
        """
        return self.create_table(name, data)

    def query(self, input_query: List[str], n_results: int, where: DIct[str, any]) -> List[str]:
        """
        Query contents from vector database based on vector similarity 

        :param input_query: list of query string
        :type input_query: List[str]
        :param n_results: no of similar documents to fetch from database
        :type n_results: int
        :param where: Optional to filter data
        :type where: Dict[str, any]
        :return: Database contents that are the result of the query
        :rtype: List[str]
        """

        # TODO

        