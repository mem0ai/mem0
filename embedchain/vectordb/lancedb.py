from typing import Any, Dict, List, Optional, Union

import pyarrow as pa

try:
    import lancedb
except ImportError:
    raise ImportError('LanceDB is required. Install with pip install "embedchain[lancedb]"') from None

from embedchain.config.vector_db.lancedb import LanceDBConfig
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.vectordb.base import BaseVectorDB


@register_deserializable
class LanceDB(BaseVectorDB):
    """
    LanceDB as vector database
    """

    def __init__(
        self,
        config: Optional[LanceDBConfig] = None,
    ):
        """LanceDB as vector database.

        :param config: LanceDB database config, defaults to None
        :type config: LanceDBConfig, optional
        """
        if config:
            self.config = config
        else:
            self.config = LanceDBConfig()

        self.client = lancedb.connect(self.config.dir or "~/.lancedb")
        self.embedder_check = True

        super().__init__(config=self.config)

    def _initialize(self):
        """
        This method is needed because `embedder` attribute needs to be set externally before it can be initialized.
        """
        if not self.embedder:
            raise ValueError(
                "Embedder not set. Please set an embedder with `_set_embedder()` function before initialization."
            )
        else:
            # check embedder function is working or not
            try:
                self.embedder.embedding_fn("Hello LanceDB")
            except Exception:
                self.embedder_check = False

        self._get_or_create_collection(self.config.collection_name)

    def _get_or_create_db(self):
        """
        Called during initialization
        """
        return self.client

    def _generate_where_clause(self, where: Dict[str, any]) -> str:
        """
        This method generate where clause using dictionary containing attributes and their values
        """

        where_filters = ""

        if len(list(where.keys())) == 1:
            where_filters = f"{list(where.keys())[0]} = {list(where.values())[0]}"
            return where_filters

        where_items = list(where.items())
        where_count = len(where_items)

        for i, (key, value) in enumerate(where_items, start=1):
            condition = f"{key} = {value} AND "
            where_filters += condition

            if i == where_count:
                condition = f"{key} = {value}"
                where_filters += condition

        return where_filters

    def _get_or_create_collection(self, table_name: str, reset=False):
        """
        Get or create a named collection.

        :param name: Name of the collection
        :type name: str
        :return: Created collection
        :rtype: Collection
        """
        if not self.embedder_check:
            schema = pa.schema(
                [
                    pa.field("doc", pa.string()),
                    pa.field("metadata", pa.string()),
                    pa.field("id", pa.string()),
                ]
            )

        else:
            schema = pa.schema(
                [
                    pa.field("vector", pa.list_(pa.float32(), list_size=self.embedder.vector_dimension)),
                    pa.field("doc", pa.string()),
                    pa.field("metadata", pa.string()),
                    pa.field("id", pa.string()),
                ]
            )

        if not reset:
            if table_name not in self.client.table_names():
                self.collection = self.client.create_table(table_name, schema=schema)

        else:
            self.client.drop_table(table_name)
            self.collection = self.client.create_table(table_name, schema=schema)

        self.collection = self.client[table_name]

        return self.collection

    def get(self, ids: Optional[List[str]] = None, where: Optional[Dict[str, any]] = None, limit: Optional[int] = None):
        """
        Get existing doc ids present in vector database

        :param ids: list of doc ids to check for existence
        :type ids: List[str]
        :param where: Optional. to filter data
        :type where: Dict[str, Any]
        :param limit: Optional. maximum number of documents
        :type limit: Optional[int]
        :return: Existing documents.
        :rtype: List[str]
        """
        if limit is not None:
            max_limit = limit
        else:
            max_limit = 3
        results = {"ids": [], "metadatas": []}

        where_clause = {}
        if where:
            where_clause = self._generate_where_clause(where)

        if ids is not None:
            records = (
                self.collection.to_lance().scanner(filter=f"id IN {tuple(ids)}", columns=["id"]).to_table().to_pydict()
            )
            for id in records["id"]:
                if where is not None:
                    result = (
                        self.collection.search(query=id, vector_column_name="id")
                        .where(where_clause)
                        .limit(max_limit)
                        .to_list()
                    )
                else:
                    result = self.collection.search(query=id, vector_column_name="id").limit(max_limit).to_list()
                results["ids"] = [r["id"] for r in result]
                results["metadatas"] = [r["metadata"] for r in result]

        return results

    def add(
        self,
        documents: List[str],
        metadatas: List[object],
        ids: List[str],
    ) -> Any:
        """
        Add vectors to lancedb database

        :param documents: Documents
        :type documents: List[str]
        :param metadatas: Metadatas
        :type metadatas: List[object]
        :param ids: ids
        :type ids: List[str]
        """
        data = []
        to_ingest = list(zip(documents, metadatas, ids))

        if not self.embedder_check:
            for doc, meta, id in to_ingest:
                temp = {}
                temp["doc"] = doc
                temp["metadata"] = str(meta)
                temp["id"] = id
                data.append(temp)
        else:
            for doc, meta, id in to_ingest:
                temp = {}
                temp["doc"] = doc
                temp["vector"] = self.embedder.embedding_fn([doc])[0]
                temp["metadata"] = str(meta)
                temp["id"] = id
                data.append(temp)

        self.collection.add(data=data)

    def _format_result(self, results) -> list:
        """
        Format LanceDB results

        :param results: LanceDB query results to format.
        :type results: QueryResult
        :return: Formatted results
        :rtype: list[tuple[Document, float]]
        """
        return results.tolist()

    def query(
        self,
        input_query: str,
        n_results: int = 3,
        where: Optional[dict[str, any]] = None,
        raw_filter: Optional[dict[str, any]] = None,
        citations: bool = False,
        **kwargs: Optional[dict[str, any]],
    ) -> Union[list[tuple[str, dict]], list[str]]:
        """
        Query contents from vector database based on vector similarity

        :param input_query: query string
        :type input_query: str
        :param n_results: no of similar documents to fetch from database
        :type n_results: int
        :param where: to filter data
        :type where: dict[str, Any]
        :param raw_filter: Raw filter to apply
        :type raw_filter: dict[str, Any]
        :param citations: we use citations boolean param to return context along with the answer.
        :type citations: bool, default is False.
        :raises InvalidDimensionException: Dimensions do not match.
        :return: The content of the document that matched your query,
        along with url of the source and doc_id (if citations flag is true)
        :rtype: list[str], if citations=False, otherwise list[tuple[str, str, str]]
        """
        if where and raw_filter:
            raise ValueError("Both `where` and `raw_filter` cannot be used together.")
        try:
            query_embedding = self.embedder.embedding_fn(input_query)[0]
            result = self.collection.search(query_embedding).limit(n_results).to_list()
        except Exception as e:
            e.message()

        results_formatted = result

        contexts = []
        for result in results_formatted:
            if citations:
                metadata = result["metadata"]
                contexts.append((result["doc"], metadata))
            else:
                contexts.append(result["doc"])
        return contexts

    def set_collection_name(self, name: str):
        """
        Set the name of the collection. A collection is an isolated space for vectors.

        :param name: Name of the collection.
        :type name: str
        """
        if not isinstance(name, str):
            raise TypeError("Collection name must be a string")
        self.config.collection_name = name
        self._get_or_create_collection(self.config.collection_name)

    def count(self) -> int:
        """
        Count number of documents/chunks embedded in the database.

        :return: number of documents
        :rtype: int
        """
        return self.collection.count_rows()

    def delete(self, where):
        return self.collection.delete(where=where)

    def reset(self):
        """
        Resets the database. Deletes all embeddings irreversibly.
        """
        # Delete all data from the collection and recreate collection
        if self.config.allow_reset:
            try:
                self._get_or_create_collection(self.config.collection_name, reset=True)
            except ValueError:
                raise ValueError(
                    "For safety reasons, resetting is disabled. "
                    "Please enable it by setting `allow_reset=True` in your LanceDbConfig"
                ) from None
        # Recreate
        else:
            print(
                "For safety reasons, resetting is disabled. "
                "Please enable it by setting `allow_reset=True` in your LanceDbConfig"
            )
