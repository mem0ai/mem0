import json
import logging
import math
from typing import Any, List, Optional, Union

import numpy as np
from sqlalchemy import JSON, Column, String, Table, func, text
from sqlalchemy.dialects.mysql import LONGTEXT

from embedchain.config import OceanBaseConfig
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.vectordb.base import BaseVectorDB

try:
    from pyobvector import VECTOR, ObVecClient
except ImportError:
    raise ImportError(
        "OceanBase requires extra dependencies. Install with `pip install --upgrade pyobvector`"
    ) from None

logger = logging.getLogger(__name__)

DEFAULT_OCEANBASE_ID_COL = "id"
DEFAULT_OCEANBASE_TEXT_COL = "text"
DEFAULT_OCEANBASE_EMBEDDING_COL = "embeddings"
DEFAULT_OCEANBASE_METADATA_COL = "metadata"
DEFAULT_OCEANBASE_VIDX_NAME = "vidx"
DEFAULT_OCEANBASE_VIDX_TYPE = "hnsw"
DEFAULT_OCEANBASE_HNSW_SEARCH_PARAM = {"efSearch": 64}


def _normalize(self, vector: List[float]) -> List[float]:
    arr = np.array(vector)
    norm = np.linalg.norm(arr)
    arr = arr / norm
    return arr.tolist()


def _euclidean_similarity(distance: float) -> float:
    return 1.0 - distance / math.sqrt(2)


def _neg_inner_product_similarity(distance: float) -> float:
    return -distance


@register_deserializable
class OceanBaseVectorDB(BaseVectorDB):
    """`OceanBase` vector store."""

    def __init__(self, config: OceanBaseConfig = None):
        if config is None:
            self.obconfig = OceanBaseConfig()
        else:
            self.obconfig = config

        self.id_field = DEFAULT_OCEANBASE_ID_COL
        self.text_field = DEFAULT_OCEANBASE_TEXT_COL
        self.embed_field = DEFAULT_OCEANBASE_EMBEDDING_COL
        self.metadata_field = DEFAULT_OCEANBASE_METADATA_COL
        self.vidx_name = DEFAULT_OCEANBASE_VIDX_NAME
        self.hnsw_ef_search = -1

        self.client = ObVecClient(
            uri=(self.obconfig.host + ":" + self.obconfig.port),
            user=self.obconfig.user,
            password=self.obconfig.passwd,
            db_name=self.obconfig.dbname,
        )

        super().__init__(config=self.obconfig)

    def _initialize(self):
        """
        This method is needed because `embedder` attribute needs to be set externally before it can be initialized.

        So it's can't be done in __init__ in one step.
        """
        if not hasattr(self, "embedder") or not self.embedder:
            raise ValueError("Cannot create a OceanBase database collection without an embedder.")
        if self.obconfig.drop_old:
            self.client.drop_table_if_exist(table_name=self.obconfig.collection_name)
        self._get_or_create_collection()

    def _get_or_create_db(self):
        """Called during initialization"""
        return self.client

    def _load_table(self):
        table = Table(
            self.obconfig.collection_name,
            self.client.metadata_obj,
            autoload_with=self.client.engine,
        )
        column_names = [column.name for column in table.columns]
        assert len(column_names) == 4

        logging.info(f"load exist table with {column_names} columns")
        self.id_field = column_names[0]
        self.text_field = column_names[1]
        self.embed_field = column_names[2]
        self.metadata_field = column_names[3]

    def _get_or_create_collection(self):
        """Get or create a named collection."""
        if self.client.check_table_exists(
            table_name=self.obconfig.collection_name,
        ):
            self._load_table()
            return

        cols = [
            Column(self.id_field, String(4096), primary_key=True, autoincrement=False),
            Column(self.text_field, LONGTEXT),
            Column(self.embed_field, VECTOR(self.embedder.vector_dimension)),
            Column(self.metadata_field, JSON),
        ]

        vidx_params = self.client.prepare_index_params()
        vidx_params.add_index(
            field_name=self.embed_field,
            index_type=DEFAULT_OCEANBASE_VIDX_TYPE,
            index_name=DEFAULT_OCEANBASE_VIDX_NAME,
            metric_type=self.obconfig.vidx_metric_type,
            params=self.obconfig.vidx_algo_params,
        )

        self.client.create_table_with_index_params(
            table_name=self.obconfig.collection_name,
            columns=cols,
            indexes=None,
            vidxs=vidx_params,
        )

    def get(self, ids: Optional[list[str]] = None, where: Optional[dict[str, any]] = None, limit: Optional[int] = None):
        """
        Get existing doc ids present in vector database

        :param ids: list of doc ids to check for existence
        :type ids: list[str]
        :param where: Optional. to filter data
        :type where: dict[str, Any]
        :param limit: Optional. maximum number of documents
        :type limit: Optional[int]
        :return: Existing documents.
        :rtype: Set[str]
        """
        res = self.client.get(
            table_name=self.obconfig.collection_name,
            ids=ids,
            where_clause=self._generate_oceanbase_filter(where),
            output_column_name=[self.id_field, self.metadata_field],
        )

        data_ids = []
        metadatas = []
        for r in res.fetchall():
            data_ids.append(r[0])
            if isinstance(r[1], str) or isinstance(r[1], bytes):
                metadatas.append(json.loads(r[1]))
            elif isinstance(r[1], dict):
                metadatas.append(r[1])
            else:
                raise ValueError("invalid json type")

        return {"ids": data_ids, "metadatas": metadatas}

    def add(
        self,
        documents: list[str],
        metadatas: list[object],
        ids: list[str],
        **kwargs: Optional[dict[str, any]],
    ):
        """Add to database"""
        batch_size = 100
        embeddings = self.embedder.embedding_fn(documents)

        total_count = len(embeddings)
        for i in range(0, total_count, batch_size):
            data = [
                {
                    self.id_field: id,
                    self.text_field: text,
                    self.embed_field: (embedding if not self.obconfig.normalize else self._normalize(embedding)),
                    self.metadata_field: metadata,
                }
                for id, text, embedding, metadata in zip(
                    ids[i : i + batch_size],
                    documents[i : i + batch_size],
                    embeddings[i : i + batch_size],
                    metadatas[i : i + batch_size],
                )
            ]
            self.client.insert(
                table_name=self.obconfig.collection_name,
                data=data,
            )

    def _parse_metric_type_str_to_dist_func(self) -> Any:
        if self.obconfig.vidx_metric_type == "l2":
            return func.l2_distance
        if self.obconfig.vidx_metric_type == "cosine":
            return func.cosine_distance
        if self.obconfig.vidx_metric_type == "inner_product":
            return func.negative_inner_product
        raise ValueError(f"Invalid vector index metric type: {self.obconfig.vidx_metric_type}")

    def _parse_distance_to_similarities(self, distance: float) -> float:
        if self.obconfig.vidx_metric_type == "l2":
            return _euclidean_similarity(distance)
        elif self.obconfig.vidx_metric_type == "inner_product":
            return _neg_inner_product_similarity(distance)
        raise ValueError(f"Metric Type {self._vidx_metric_type} is not supported")

    def query(
        self,
        input_query: str,
        n_results: int,
        where: dict[str, Any],
        citations: bool = False,
        param: Optional[dict] = None,
        **kwargs: Optional[dict[str, Any]],
    ) -> Union[list[tuple[str, dict]], list[str]]:
        """
        Query contents from vector database based on vector similarity

        :param input_query: query string
        :type input_query: str
        :param n_results: no of similar documents to fetch from database
        :type n_results: int
        :param where: to filter data
        :type where: dict[str, Any]
        :param citations: we use citations boolean param to return context along with the answer.
        :type citations: bool, default is False.
        :param param: search parameters for hnsw.
        :type param: Optional[dict]
        :return: The content of the document that matched your query,
        along with url of the source and doc_id (if citations flag is true)
        :rtype: list[str], if citations=False, otherwise list[tuple[str, dict]]
        """
        search_param = param if param is not None else DEFAULT_OCEANBASE_HNSW_SEARCH_PARAM
        ef_search = search_param.get("efSearch", DEFAULT_OCEANBASE_HNSW_SEARCH_PARAM["efSearch"])
        if ef_search != self.hnsw_ef_search:
            self.client.set_ob_hnsw_ef_search(ef_search)
            self.hnsw_ef_search = ef_search

        input_query_vector = self.embedder.embedding_fn([input_query])
        res = self.client.ann_search(
            table_name=self.obconfig.collection_name,
            vec_data=(input_query_vector[0] if not self.obconfig.normalize else _normalize(input_query_vector[0])),
            vec_column_name=self.embed_field,
            distance_func=self._parse_metric_type_str_to_dist_func(),
            with_dist=True,
            topk=n_results,
            output_column_names=[self.text_field, self.metadata_field],
            where_clause=self._generate_oceanbase_filter(where),
            **kwargs,
        )

        contexts = []
        for r in res:
            context = r[0]
            if isinstance(r[1], str) or isinstance(r[1], bytes):
                metadata = json.loads(r[1])
            elif isinstance(r[1], dict):
                metadata = r[1]
            else:
                raise ValueError("invalid json type")
            score = self._parse_distance_to_similarities(r[2])

            if citations:
                metadata["score"] = score
                contexts.append((context, metadata))
            else:
                contexts.append(context)
        return contexts

    def count(self) -> int:
        """
        Count number of documents/chunks embedded in the database.

        :return: number of documents
        :rtype: int
        """
        res = self.client.perform_raw_text_sql(f"SELECT COUNT(*) FROM {self.obconfig.collection_name}")
        return res.fetchall()[0][0]

    def reset(self, collection_names: list[str] = None):
        """
        Resets the database. Deletes all embeddings irreversibly.
        """
        if collection_names:
            for collection_name in collection_names:
                self.client.drop_table_if_exist(table_name=collection_name)

    def set_collection_name(self, name: str):
        """
        Set the name of the collection. A collection is an isolated space for vectors.

        :param name: Name of the collection.
        :type name: str
        """
        if not isinstance(name, str):
            raise TypeError("Collection name must be a string")
        self.obconfig.collection_name = name

    def _generate_oceanbase_filter(self, where: dict[str, str]):
        if len(where.keys()) == 0:
            return None
        operands = []
        for key, value in where.items():
            operands.append(f"({self.metadata_field}->'$.{key}' = '{value}')")
        return [text(" and ".join(operands))]
