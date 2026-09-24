import json
import logging
from typing import Any, Dict, List, Optional

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)

try:
    from pyvastbase import (
        Collection,
        CollectionSchema,
        DataType,
        DistanceType,
        FieldSchema,
        IndexParams,
        IndexType,
        connect,
        create_database,
        create_vector_index,
        describe_collection,
        drop_collection,
        has_collection,
        list_collections,
    )
except ImportError:
    raise ImportError(
        "The 'pyvastbase' library is required. Install it with: pip install pyvastbase"
    )


class OutputData:
    def __init__(self, id: Optional[str] = None, score: Optional[float] = None, payload: Optional[dict] = None):
        self.id = id
        self.score = score
        self.payload = payload


def _build_filter_expr(filters: Optional[Dict]) -> Optional[str]:
    if not filters:
        return None

    parts = []
    for key, value in filters.items():
        if key == "$or":
            or_parts = []
            for sub in value:
                expr = _build_filter_expr(sub)
                if expr:
                    or_parts.append(expr)
            if or_parts:
                parts.append("(" + " OR ".join(or_parts) + ")")
            continue

        if key == "$not":
            not_parts = []
            for sub in value:
                expr = _build_filter_expr(sub)
                if expr:
                    not_parts.append(expr)
            if not_parts:
                parts.append("NOT (" + " OR ".join(not_parts) + ")")
            continue

        if value == "*":
            parts.append(f"payload ? '{key}'")
            continue

        if isinstance(value, dict):
            for op, op_value in value.items():
                if op == "eq":
                    parts.append(f"payload->>'{key}' = '{op_value}'")
                elif op == "ne":
                    parts.append(f"payload->>'{key}' != '{op_value}'")
                elif op == "gt":
                    parts.append(f"(payload->>'{key}')::numeric > {float(op_value)}")
                elif op == "gte":
                    parts.append(f"(payload->>'{key}')::numeric >= {float(op_value)}")
                elif op == "lt":
                    parts.append(f"(payload->>'{key}')::numeric < {float(op_value)}")
                elif op == "lte":
                    parts.append(f"(payload->>'{key}')::numeric <= {float(op_value)}")
                elif op == "in":
                    vals = ", ".join(f"'{v}'" for v in op_value)
                    parts.append(f"payload->>'{key}' IN ({vals})")
                elif op == "nin":
                    vals = ", ".join(f"'{v}'" for v in op_value)
                    parts.append(f"payload->>'{key}' NOT IN ({vals})")
                elif op == "contains":
                    escaped = str(op_value).replace("'", "''")
                    parts.append(f"payload->>'{key}' LIKE '%{escaped}%'")
                elif op == "icontains":
                    escaped = str(op_value).replace("'", "''")
                    parts.append(f"payload->>'{key}' ILIKE '%{escaped}%'")
                else:
                    raise ValueError(f"Unsupported filter operator: {op}")
        elif isinstance(value, list):
            vals = ", ".join(f"'{v}'" for v in value)
            parts.append(f"payload->>'{key}' IN ({vals})")
        else:
            if isinstance(value, bool):
                parts.append(f"payload->>'{key}' = '{json.dumps(value)}'")
            else:
                parts.append(f"payload->>'{key}' = '{value}'")

    return " AND ".join(parts) if parts else None


class Vastbase(VectorStoreBase):
    def __init__(
        self,
        dbname: str = "mem0",
        collection_name: str = "mem0",
        embedding_model_dims: int = 1536,
        user: Optional[str] = None,
        password: Optional[str] = None,
        host: Optional[str] = "localhost",
        port: Optional[int] = 5432,
        m: int = 16,
        ef_construction: int = 200,
        ef_search: int = 100,
        quantizer: Optional[str] = None,
        parallel_workers: int = 0,
        connection_string: Optional[str] = None,
    ):
        self.collection_name = collection_name
        self.embedding_model_dims = embedding_model_dims
        self.m = m
        self.ef_construction = ef_construction
        self.ef_search = ef_search
        self.quantizer = quantizer
        self.parallel_workers = parallel_workers
        self._connected = False

        if connection_string:
            self._connect_kwargs = {"connection_string": connection_string}
        else:
            self._connect_kwargs = {
                "host": host,
                "port": port,
                "user": user,
                "password": password,
                "database": dbname,
            }

        self._ensure_connected()
        self._ensure_collection()

    def _ensure_connected(self):
        if self._connected:
            return
        try:
            connect(**self._connect_kwargs)
            self._connected = True
            logger.info("Connected to Vastbase database")
        except Exception as e:
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                self._connected = True
                logger.info("Already connected to Vastbase database")
            else:
                raise

    def _ensure_collection(self):
        try:
            if has_collection(self.collection_name):
                self.collection = Collection(self.collection_name)
                return
        except Exception:
            pass
        self.create_col()

    def create_col(self, name=None, vector_size=None, distance=None):
        col_name = name or self.collection_name
        dims = vector_size or self.embedding_model_dims

        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=36, is_primary_key=True),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dims),
            FieldSchema(name="payload", dtype=DataType.JSON),
        ]
        schema = CollectionSchema(name=col_name, fields=fields)

        collection = Collection(col_name, schema=schema)
        collection.create()
        logger.info(f"Created collection '{col_name}' with {dims} dimensions")

        index_params = IndexParams(
            field_name="vector",
            index_type=IndexType.GRAPH_INDEX,
            metric_type=DistanceType.COSINE,
            params={
                "m": self.m,
                "ef_construction": self.ef_construction,
            },
        )
        if self.quantizer:
            index_params.params["quantizer"] = self.quantizer
        if self.parallel_workers > 0:
            index_params.params["parallel_workers"] = self.parallel_workers

        collection.create_index(field_name="vector", index_params=index_params)
        logger.info(f"Created graph_index on collection '{col_name}' (m={self.m}, ef_construction={self.ef_construction})")

        self.collection = collection

    def insert(self, vectors, payloads=None, ids=None):
        self._ensure_connected()
        data = []
        for i, (vid, vec) in enumerate(zip(ids, vectors)):
            record = {
                "id": str(vid),
                "vector": vec,
                "payload": payloads[i] if payloads else {},
            }
            data.append(record)

        self.collection.insert(data)
        logger.info(f"Inserted {len(data)} vectors into '{self.collection_name}'")

    def search(self, query="", vectors=None, top_k=5, filters=None):
        self._ensure_connected()
        if vectors is None:
            return []

        query_vectors = [vectors] if isinstance(vectors[0], float) else vectors

        filter_expr = _build_filter_expr(filters)

        search_params = {
            "ef": self.ef_search,
        }

        results = self.collection.search(
            data=query_vectors,
            anns_field="vector",
            limit=top_k,
            param=search_params,
            filter=filter_expr,
            output_fields=["payload", "id"],
        )

        output = []
        if results and len(results) > 0:
            for hit in results[0]:
                distance = float(hit.distance)
                score = max(0.0, min(1.0, 1.0 - distance))
                payload = hit.data.get("payload", {})
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except (json.JSONDecodeError, TypeError):
                        payload = {}
                vid = hit.id or hit.data.get("id", "")
                output.append(OutputData(id=str(vid), score=score, payload=payload))

        return output

    def delete(self, vector_id):
        self._ensure_connected()
        self.collection.delete(filter=f"id = '{vector_id}'")
        logger.info(f"Deleted vector {vector_id} from '{self.collection_name}'")

    def update(self, vector_id, vector=None, payload=None):
        self._ensure_connected()
        if vector is not None and payload is not None:
            self.collection.upsert([{"id": str(vector_id), "vector": vector, "payload": payload}])
        elif vector is not None:
            existing = self.get(vector_id)
            existing_payload = existing.payload if existing else {}
            self.collection.upsert([{"id": str(vector_id), "vector": vector, "payload": existing_payload}])
        elif payload is not None:
            existing = self.get(vector_id)
            if existing:
                merged = {**(existing.payload or {}), **payload}
                # Need to re-fetch vector for upsert; use query with id filter
                try:
                    rows = self.collection.query(
                        filter=f"id = '{vector_id}'",
                        output_fields=["vector"],
                        limit=1,
                    )
                    if rows:
                        vec = rows[0].get("vector", [])
                        self.collection.upsert([{"id": str(vector_id), "vector": vec, "payload": merged}])
                except Exception as e:
                    logger.warning(f"Update payload failed: {e}")

    def get(self, vector_id):
        self._ensure_connected()
        try:
            results = self.collection.get(ids=[str(vector_id)], output_fields=["payload"])
            if results:
                record = results[0]
                payload = record.get("payload", {})
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except (json.JSONDecodeError, TypeError):
                        payload = {}
                return OutputData(id=str(record.get("id", vector_id)), score=None, payload=payload)
        except Exception as e:
            logger.debug(f"Get failed for {vector_id}: {e}")
        return None

    def list_cols(self):
        self._ensure_connected()
        return list_collections()

    def delete_col(self):
        self._ensure_connected()
        try:
            drop_collection(self.collection_name)
            logger.info(f"Dropped collection '{self.collection_name}'")
        except Exception as e:
            logger.warning(f"Failed to drop collection: {e}")

    def col_info(self):
        self._ensure_connected()
        try:
            info = describe_collection(self.collection_name)
            return {
                "name": self.collection_name,
                "count": info.get("row_count", 0),
                "size": None,
            }
        except Exception as e:
            logger.warning(f"Failed to get collection info: {e}")
            return {"name": self.collection_name, "count": 0, "size": None}

    def list(self, filters=None, top_k=100):
        self._ensure_connected()
        filter_expr = _build_filter_expr(filters)
        try:
            results = self.collection.query(
                filter=filter_expr or "",
                output_fields=["payload"],
                limit=top_k,
            )
            output = []
            for r in results:
                payload = r.get("payload", {})
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except (json.JSONDecodeError, TypeError):
                        payload = {}
                output.append(OutputData(id=str(r.get("id", "")), score=None, payload=payload))
            return [output]
        except Exception as e:
            logger.debug(f"List failed: {e}")
            return [[]]

    def reset(self):
        logger.warning(f"Resetting collection '{self.collection_name}'...")
        self.delete_col()
        self.create_col()
