import logging
from typing import Any, Dict, List, Optional

from lancedb import connect, create_table, delete, open_table

from embedchain.helper.json_serializable import register_deserializable
from embedchain.vectordb.base import BaseVectorDB

@register_deserializable
class LanceDb(BaseVectorDB):
    """Vector database using LanceDB"""
    """
    Example:
    ..code - block:: python

    db = lancedb.connect('./lancedb')
    table = db.open_table('my_table')
    vectorstore = LanceDB(table, embedding_function)
    vectorstore.add_texts(['text1', 'text2'])
    result = vectorstore.similarity_search('text1') """

    def __init__(
            self,
            uri: str,
            table_name: str = "lance_table",
            **kwargs: Any,
    ) -> None:
        """Initialize a new LanceDB connection"""
        try:
            import lancedb
        except ImportError:
            raise ImportError(
            "could not import lancedb python package. "
            "please install it with `pip install lancedb`."
        )
        if not isinstance(connection, lancedb.db.LanceTable):
            raise ValueError(
                "connection should be an instance of lancedb.db.LanceTable, ",
                f"got{type(connection)}"
            )
        self.connection = lancedb.connect(uri)
        self.uri = uri
        self.table_name = table_name

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
        :type metadatas: Metadatas
        :type metadatas: List[object]
        :param ids: ids
        :type ids: List[str]
        """

        if self.table_name in self.connection.table_names():
            tbl = self.connection.open_table(self.table_name)
            tbl.add(documents)
        else:
            self.connection.create_table(self.table_name, documents)

    def delete(self, where) -> None:
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