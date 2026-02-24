import json
import logging
import os
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from mem0.vector_stores.base import VectorStoreBase

try:
    from zvec import (
        Collection,
        CollectionOption,
        CollectionSchema,
        DataType,
        Doc,
        FieldSchema,
        FlatIndexParam,
        MetricType,
        VectorQuery,
        VectorSchema,
        create_and_open,
        open as open_collection,
    )
except ImportError:
    raise ImportError("The 'zvec' library is required. Please install it using 'pip install zvec'.")

logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: Optional[str]
    score: Optional[float]
    payload: Optional[Dict[str, Any]]


class Zvec(VectorStoreBase):
    VECTOR_FIELD = "embedding"
    METADATA_JSON_FIELD = "metadata_json"
    CORE_PAYLOAD_FIELDS = (
        "data",
        "hash",
        "created_at",
        "updated_at",
        "user_id",
        "agent_id",
        "run_id",
        "actor_id",
        "role",
    )
    SUPPORTED_FILTER_FIELDS = {*CORE_PAYLOAD_FIELDS}
    SUPPORTED_FILTER_OPERATORS = {"eq", "ne", "gt", "gte", "lt", "lte", "in", "nin"}

    def __init__(
        self,
        collection_name: str,
        embedding_model_dims: int,
        path: str = "/tmp/zvec",
        client: Optional[Collection] = None,
        read_only: bool = False,
        enable_mmap: bool = True,
    ):
        self.collection_name = collection_name
        self.embedding_model_dims = embedding_model_dims
        self.path = path
        self.read_only = read_only
        self.enable_mmap = enable_mmap
        self.collection_path = os.path.join(self.path, self.collection_name)
        self.client = client

        if self.client is None:
            self.create_col(vector_size=self.embedding_model_dims, on_disk=enable_mmap)
        else:
            self.collection_path = getattr(self.client, "path", self.collection_path)

    def _collection_option(self) -> CollectionOption:
        return CollectionOption(read_only=self.read_only, enable_mmap=self.enable_mmap)

    def _collection_schema(self, vector_size: int) -> CollectionSchema:
        scalar_fields = [
            FieldSchema("data", DataType.STRING, nullable=True),
            FieldSchema("hash", DataType.STRING, nullable=True),
            FieldSchema("created_at", DataType.STRING, nullable=True),
            FieldSchema("updated_at", DataType.STRING, nullable=True),
            FieldSchema("user_id", DataType.STRING, nullable=True),
            FieldSchema("agent_id", DataType.STRING, nullable=True),
            FieldSchema("run_id", DataType.STRING, nullable=True),
            FieldSchema("actor_id", DataType.STRING, nullable=True),
            FieldSchema("role", DataType.STRING, nullable=True),
            FieldSchema(self.METADATA_JSON_FIELD, DataType.STRING, nullable=True),
        ]

        vector_field = VectorSchema(
            self.VECTOR_FIELD,
            DataType.VECTOR_FP32,
            dimension=vector_size,
            index_param=FlatIndexParam(metric_type=MetricType.COSINE),
        )

        return CollectionSchema(name=self.collection_name, fields=scalar_fields, vectors=[vector_field])

    @staticmethod
    def _serialize_value(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False)

    def _payload_to_fields(self, payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        payload = payload or {}
        fields: Dict[str, Any] = {}
        custom_payload: Dict[str, Any] = {}

        for key, value in payload.items():
            if key in self.CORE_PAYLOAD_FIELDS:
                fields[key] = self._serialize_value(value)
            else:
                custom_payload[key] = value

        if custom_payload:
            fields[self.METADATA_JSON_FIELD] = json.dumps(custom_payload, ensure_ascii=False)

        return fields

    def _doc_to_output(self, doc: Doc, include_score: bool = True) -> OutputData:
        payload = {}
        fields = doc.fields or {}

        for key in self.CORE_PAYLOAD_FIELDS:
            if key in fields and fields[key] is not None:
                payload[key] = fields[key]

        metadata_json = fields.get(self.METADATA_JSON_FIELD)
        if metadata_json:
            try:
                additional_metadata = json.loads(metadata_json)
                if isinstance(additional_metadata, dict):
                    payload.update(additional_metadata)
            except (TypeError, ValueError):
                logger.warning("Failed to deserialize zvec metadata_json for document %s", doc.id)

        score = float(doc.score) if include_score and doc.score is not None else None
        return OutputData(id=doc.id, score=score, payload=payload)

    @staticmethod
    def _quote_filter_value(value: Any) -> str:
        if isinstance(value, str):
            escaped = value.replace("\\", "\\\\").replace("'", "\\'")
            return f"'{escaped}'"
        if isinstance(value, bool):
            return "true" if value else "false"
        if value is None:
            return "null"
        return str(value)

    def _translate_filters(self, filters: Optional[Dict[str, Any]]) -> Optional[str]:
        if not filters:
            return None

        if "$or" in filters or "$not" in filters:
            raise ValueError("Zvec vector store currently supports AND filters only.")

        conditions: List[str] = []
        for key, value in filters.items():
            if key.startswith("$"):
                raise ValueError(f"Unsupported logical filter operator for zvec: {key}")
            if key not in self.SUPPORTED_FILTER_FIELDS:
                raise ValueError(
                    f"Unsupported filter field for zvec: {key}. Supported fields: {sorted(self.SUPPORTED_FILTER_FIELDS)}"
                )

            if isinstance(value, dict):
                for operator, operator_value in value.items():
                    if operator not in self.SUPPORTED_FILTER_OPERATORS:
                        raise ValueError(
                            f"Unsupported filter operator for zvec: {operator}. Supported operators: {sorted(self.SUPPORTED_FILTER_OPERATORS)}"
                        )
                    if operator == "eq":
                        conditions.append(f"{key} = {self._quote_filter_value(operator_value)}")
                    elif operator == "ne":
                        conditions.append(f"{key} != {self._quote_filter_value(operator_value)}")
                    elif operator == "gt":
                        conditions.append(f"{key} > {self._quote_filter_value(operator_value)}")
                    elif operator == "gte":
                        conditions.append(f"{key} >= {self._quote_filter_value(operator_value)}")
                    elif operator == "lt":
                        conditions.append(f"{key} < {self._quote_filter_value(operator_value)}")
                    elif operator == "lte":
                        conditions.append(f"{key} <= {self._quote_filter_value(operator_value)}")
                    elif operator in {"in", "nin"}:
                        if not isinstance(operator_value, list) or not operator_value:
                            raise ValueError(f"Filter operator '{operator}' expects a non-empty list.")
                        values = ", ".join(self._quote_filter_value(v) for v in operator_value)
                        keyword = "in" if operator == "in" else "not in"
                        conditions.append(f"{key} {keyword} ({values})")
            else:
                conditions.append(f"{key} = {self._quote_filter_value(value)}")

        return " and ".join(conditions) if conditions else None

    def create_col(self, vector_size: int, on_disk: bool, distance: MetricType = MetricType.COSINE):  # noqa: ARG002
        os.makedirs(self.path, exist_ok=True)
        option = CollectionOption(read_only=self.read_only, enable_mmap=on_disk)

        if os.path.isdir(self.collection_path):
            try:
                self.client = open_collection(path=self.collection_path, option=option)
                return
            except Exception as err:
                logger.debug("Failed to open existing zvec collection at %s: %s", self.collection_path, err)

        schema = self._collection_schema(vector_size)
        try:
            self.client = create_and_open(path=self.collection_path, schema=schema, option=option)
        except Exception as create_err:
            logger.debug("Failed to create zvec collection at %s: %s", self.collection_path, create_err)
            self.client = open_collection(path=self.collection_path, option=option)

    def insert(self, vectors: List[list], payloads: Optional[List[Dict]] = None, ids: Optional[List[str]] = None):
        docs: List[Doc] = []
        payloads = payloads or [{} for _ in vectors]

        for idx, vector in enumerate(vectors):
            doc_id = str(ids[idx]) if ids is not None else str(idx)
            fields = self._payload_to_fields(payloads[idx])
            docs.append(Doc(id=doc_id, fields=fields, vectors={self.VECTOR_FIELD: vector}))

        self.client.upsert(docs)

    def search(self, query: str, vectors: List[list], limit: int = 5, filters: Optional[Dict] = None) -> List[OutputData]:  # noqa: ARG002
        query_vector = vectors
        if isinstance(vectors, list) and vectors and isinstance(vectors[0], list):
            query_vector = vectors[0]

        filter_expression = self._translate_filters(filters)
        vector_query = VectorQuery(field_name=self.VECTOR_FIELD, vector=query_vector)
        docs = self.client.query(vectors=vector_query, topk=limit, filter=filter_expression, include_vector=False)
        return [self._doc_to_output(doc) for doc in docs]

    def delete(self, vector_id: str):
        self.client.delete(str(vector_id))

    def update(self, vector_id: str, vector: Optional[list] = None, payload: Optional[dict] = None):
        if vector is None and payload is None:
            return
        fields = self._payload_to_fields(payload) if payload is not None else {}
        vectors = {self.VECTOR_FIELD: vector} if vector is not None else {}
        self.client.update(Doc(id=str(vector_id), fields=fields, vectors=vectors))

    def get(self, vector_id: str) -> Optional[OutputData]:
        docs = self.client.fetch([str(vector_id)])
        if not docs:
            return None

        doc = docs.get(str(vector_id))
        if doc is None:
            return None
        return self._doc_to_output(doc, include_score=False)

    def list_cols(self) -> List[str]:
        if not os.path.isdir(self.path):
            return []
        return [name for name in os.listdir(self.path) if os.path.isdir(os.path.join(self.path, name))]

    def delete_col(self):
        if self.client is None:
            return
        self.client.destroy()
        self.client = None

    def col_info(self):
        if self.client is None:
            return None
        return self.client.stats

    def list(self, filters: Optional[Dict] = None, limit: int = 100) -> List[List[OutputData]]:
        filter_expression = self._translate_filters(filters)
        docs = self.client.query(topk=limit, filter=filter_expression, include_vector=False)
        return [[self._doc_to_output(doc, include_score=False) for doc in docs]]

    def reset(self):
        logger.warning("Resetting index %s...", self.collection_name)
        self.delete_col()
        self.create_col(vector_size=self.embedding_model_dims, on_disk=self.enable_mmap)
