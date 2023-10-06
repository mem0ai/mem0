import logging
from typing import Any, Dict, List, Optional, Set

from lancedb import connect, create_table, Table
from langchain.docstore.document import Document

from embedchain.config import LanceDBConfig
from embedchain.helper.json_serializable import register_deserializable
from embedchain.vectordb.base import BaseVectorDB


try:
    import lancedb
    from lancedb import connect, create_table, delete, open_table
except ImportError:
    raise ImportError(
        "LanceDb requirese extra dependencies. Install with `pip install --upgrade embedchain[lancedb]`"
            ) from None


@register_deserializable
class LanceDb(BaseVectorDB):
    """
    LanceDB as vector database
    """

    def __init__(
        self,
        config: Optional[LanceDBConfig] = None,
    ):
        """Initialize a new LanceDB connection

        :param config: LanceDB database config, defaults to None
        :type config: LanceDBConfig, optional

        """

        if config:
            self.config = config
        else:
            self.config = LanceDBConfig()

        self.connection = lancedb.connect(self.config.uri, **self.config.kwargs)
        super().__init__(config=self.config)

    def _initialize(self):
        """
        this method is needed because 'embedder' attribute needs to be externally set
        """
        if not self.embedder:
            raise ValueError("Embedder not set. Please set an embedder with `set_embedder` before initialization.")
        self._get_or_create_collection(self.config.table_name)

    def _get_or_create_db(self):
        """called during initalization"""
        return self.connection

    def _get_or_create_collection(self, name: str) -> Table:
        """
        get or create a named table

        :param name: Name of the table
        :type name: str
        :raises ValueError: No Embedder configured
        :return: created table
        :rtype: Table
        """
        if not hasattr(self, "embedder") or not self.embedder:
            raise ValueError("Cannot create a LanceDB database Table without an embedder.")
        self.table = self.connect.get_or_create_collection(
            name=name,
            embedding_function=self.embedder.embedding_fn,
            )
        return self.table

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


    def query(self, input_query: List[str], where: Dict[str, any]) -> List[str]:
        """
        Query contents from vector database based on vector similarity 

        :param input_query: list of query string 
        :type input_query: List[str]
        :param where: Optional to filter data
        :type where: Dict[str, any]
        :return: Database contents that are the result of the query
        :rtype: List[str]
        """
        result = self.table.search(query=input_query, vector_column_name=where)
        return result



    def delete(self, where) -> None:
        """ Delete something from the table 

        :param where: Documents
        :type where: str

        """
        return self.connection.delete(where=where)
  