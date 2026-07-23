import json
import logging
import time
from typing import Dict, List, Optional, Any

from mem0.vector_stores.base import VectorStoreBase
from pydantic import BaseModel

try:
    import tcvectordb
except ImportError:
    raise ImportError("The 'tcvectordb' library is required. Please install it using 'pip install tcvectordb'.")


from tcvectordb.model import enum, index as vdb_index
from tcvectordb.model.enum import ReadConsistency
from tcvectordb.model.index import Index, VectorIndex, FilterIndex, SparseIndex
from tcvectordb.model.document import Filter, Document, SearchParams


logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: Optional[str]  # memory id
    score: Optional[float]  # distance
    payload: Optional[Dict]  # metadata


class TencentVectorDB(VectorStoreBase):
    def __init__(
        self,
        url: str,
        key: str,
        collection_name: str,
        embedding_model_dims: int,
        metric_type: str = "COSINE",
        username: str = "root",
        database_name: str = "default",
        read_consistency: str = "EVENTUAL_CONSISTENCY",
        timeout: int = 30,
        shard: int = 1,
        replicas: int = 2,
        index_type: str = "HNSW",
        index_params: Optional[Dict[str, Any]] = None,
        sparse_language: str = "en",
    ):
        """Initialize the Tencent Vector DB client.

        Args:
            url (str): Connection URL.
            key (str): Connection Key/Token.
            collection_name (str): Collection name.
            embedding_model_dims (int): Dimension of dense vector.
            metric_type (str): Metric type. Defaults to COSINE.
            username (str): Username. Defaults to root.
            database_name (str): Database name. Defaults to default.
            read_consistency (str): Read consistency level.
            timeout (int): Timeout in seconds.
            shard (int): Number of shards.
            replicas (int): Number of replicas.
            index_type (str): Dense vector index type.
            index_params (dict): Optional parameters dictionary for the index.
            sparse_language (str): Language parameter for sparse vector BM25 encoder. Supported values are "zh" and "en". Defaults to "en".
        """
        self.collection_name = collection_name
        self.embedding_model_dims = embedding_model_dims
        self.metric_type = metric_type
        self.database_name = database_name
        self.shard = shard
        self.replicas = replicas
        self.index_type = index_type
        self.index_params = index_params
        self.sparse_language = sparse_language
        self._bm25_encoder = None

        read_consistency_val = ReadConsistency.__members__.get(read_consistency, ReadConsistency.EVENTUAL_CONSISTENCY)
        self.client = tcvectordb.RPCVectorDBClient(
            url=url,
            key=key,
            username=username,
            read_consistency=read_consistency_val,
            timeout=timeout,
        )

        try:
            self.client.create_database(database_name)
        except Exception:
            pass

        self.db = self.client.database(database_name)
        self.collection = None
        self.create_col(
            name=self.collection_name,
            vector_size=self.embedding_model_dims,
            distance=self.metric_type,
        )

    def _get_index_params(self, index_type_val: enum.IndexType) -> Any:
        """Helper to get parameters object for the specific index type."""
        if self.index_params and not isinstance(self.index_params, dict):
            # If the user passed a pre-constructed param instance, use it directly
            return self.index_params

        p_dict = self.index_params or {}

        if index_type_val in (enum.IndexType.HNSW, enum.IndexType.BIN_HNSW):
            m_val = p_dict.get("m", p_dict.get("M", 16))
            efc_val = p_dict.get("efconstruction", p_dict.get("efConstruction", 200))
            return vdb_index.HNSWParams(m=m_val, efconstruction=efc_val)

        elif index_type_val == enum.IndexType.IVF_FLAT:
            nlist_val = p_dict.get("nlist", 1024)
            return vdb_index.IVFFLATParams(nlist=nlist_val)

        elif index_type_val == enum.IndexType.IVF_PQ:
            nlist_val = p_dict.get("nlist", 1024)
            m_val = p_dict.get("m", p_dict.get("M", 8))
            return vdb_index.IVFPQParams(nlist=nlist_val, m=m_val)

        elif index_type_val == enum.IndexType.IVF_SQ4:
            nlist_val = p_dict.get("nlist", 1024)
            return vdb_index.IVFSQ4Params(nlist=nlist_val)

        elif index_type_val == enum.IndexType.IVF_SQ8:
            nlist_val = p_dict.get("nlist", 1024)
            return vdb_index.IVFSQ8Params(nlist=nlist_val)

        elif index_type_val == enum.IndexType.IVF_SQ16:
            nlist_val = p_dict.get("nlist", 1024)
            return vdb_index.IVFSQ16Params(nlist=nlist_val)

        elif index_type_val == enum.IndexType.IVF_RABITQ:
            nlist_val = p_dict.get("nlist", 1024)
            bits_val = p_dict.get("bits")
            return vdb_index.IVFRABITQParams(nlist=nlist_val, bits=bits_val)

        return p_dict if p_dict else None

    def create_col(self, name, vector_size, distance="COSINE"):
        """Create collection if not exists."""
        if self.db.exists_collection(name):
            logger.info(f"Collection {name} already exists. Skipping creation.")
            self.collection = self.db.collection(name)
            return

        metric_type_val = enum.MetricType.COSINE
        if distance == "L2":
            metric_type_val = enum.MetricType.L2
        elif distance == "IP":
            metric_type_val = enum.MetricType.IP

        index_type_val = enum.IndexType.__members__.get(self.index_type, enum.IndexType.HNSW)
        index_params_val = self._get_index_params(index_type_val)

        index = Index(
            FilterIndex("id", enum.FieldType.String, enum.IndexType.PRIMARY_KEY),
            VectorIndex(
                "vector",
                vector_size,
                index_type_val,
                metric_type_val,
                index_params_val,
            ),
            FilterIndex("text", enum.FieldType.String, enum.IndexType.FILTER),
            SparseIndex("sparse_vector", metric_type=enum.MetricType.IP)
        )

        for field_name in ["user_id", "run_id", "agent_id", "hash"]:
            index.add(FilterIndex(field_name, enum.FieldType.String, enum.IndexType.FILTER))
        index.add(FilterIndex("metadata", enum.FieldType.String, enum.IndexType.FILTER))

        try:
            self.collection = self.db.create_collection_if_not_exists(
                name=name,
                shard=self.shard,
                replicas=self.replicas,
                description="Collection for Mem0",
                index=index,
            )
            time.sleep(10)
        except Exception as e:
            logger.info(f"Failed to create collection {name}: {e}. Trying to load existing collection.")
            self.collection = self.db.collection(name)

    def _get_bm25_encoder(self):
        """Lazy-load the BM25 sparse text encoder (tcvdb-text)."""
        if self._bm25_encoder is None:
            try:
                from tcvdb_text.encoder.bm25 import BM25Encoder
                self._bm25_encoder = BM25Encoder.default(self.sparse_language)
                logger.info("BM25 encoder loaded (tcvdb-text)")
            except ImportError:
                logger.warning("tcvdb-text not installed - BM25 keyword search disabled.")
                self._bm25_encoder = False  # sentinel
            except Exception as e:
                logger.warning(f"Failed to load BM25 encoder: {e}")
                self._bm25_encoder = False
        return self._bm25_encoder if self._bm25_encoder is not False else None

    def _dict_to_tencent_expr(self, filters: dict) -> str:
        """
        Convert Mem0 filter dictionary (potentially with nested operators)
        into a Tencent Vector DB filter expression string.
        """
        if not filters:
            return ""

        # Normalize logical operators
        key_map = {"$or": "OR", "$not": "NOT", "$and": "AND"}
        normalized = {}
        for k, v in filters.items():
            norm_key = key_map.get(k, k)
            if norm_key not in normalized:
                normalized[norm_key] = v

        conds = []

        for key, value in normalized.items():
            if key == "AND":
                if isinstance(value, list):
                    sub_conds = [self._dict_to_tencent_expr(sub) for sub in value]
                    sub_conds = [c for c in sub_conds if c]
                    if sub_conds:
                        conds.append("(" + ") and (".join(sub_conds) + ")")
            elif key == "OR":
                if isinstance(value, list):
                    sub_conds = [self._dict_to_tencent_expr(sub) for sub in value]
                    sub_conds = [c for c in sub_conds if c]
                    if sub_conds:
                        conds.append("(" + ") or (".join(sub_conds) + ")")
            elif key == "NOT":
                if isinstance(value, list):
                    sub_conds = [self._dict_to_tencent_expr(sub) for sub in value]
                    sub_conds = [c for c in sub_conds if c]
                    if sub_conds:
                        conds.append("not (" + ") and not (".join(sub_conds) + ")")
            else:
                # Field condition
                field_expr = self._build_field_expression(key, value)
                if field_expr:
                    conds.append(field_expr)

        return " and ".join(conds) if conds else ""

    def _build_field_expression(self, key: str, value: Any) -> str:
        if value == "*":
            return ""

        if not isinstance(value, dict):
            if isinstance(value, list):
                formatted_vals = [self._format_value(v) for v in value]
                return f"{key} in ({', '.join(formatted_vals)})"
            return f"{key} = {self._format_value(value)}"

        sub_exprs = []
        for op, val in value.items():
            if op == "eq":
                sub_exprs.append(f"{key} = {self._format_value(val)}")
            elif op == "ne":
                sub_exprs.append(f"{key} != {self._format_value(val)}")
            elif op == "gt":
                sub_exprs.append(f"{key} > {self._format_value(val)}")
            elif op == "gte":
                sub_exprs.append(f"{key} >= {self._format_value(val)}")
            elif op == "lt":
                sub_exprs.append(f"{key} < {self._format_value(val)}")
            elif op == "lte":
                sub_exprs.append(f"{key} <= {self._format_value(val)}")
            elif op == "in":
                vals = val if isinstance(val, list) else [val]
                formatted_vals = [self._format_value(v) for v in vals]
                sub_exprs.append(f"{key} in ({', '.join(formatted_vals)})")
            elif op == "nin":
                vals = val if isinstance(val, list) else [val]
                formatted_vals = [self._format_value(v) for v in vals]
                sub_exprs.append(f"{key} not in ({', '.join(formatted_vals)})")
            elif op in ("contains", "icontains"):
                vals = val if isinstance(val, list) else [val]
                formatted_vals = [self._format_value(v) for v in vals]
                sub_exprs.append(f"{key} include ({', '.join(formatted_vals)})")
            
        return " and ".join(sub_exprs) if sub_exprs else ""

    def _format_value(self, val: Any) -> str:
        if isinstance(val, str):
            escaped = val.replace('"', '\\"')
            return f'"{escaped}"'
        elif isinstance(val, bool):
            return str(val).lower()
        else:
            return str(val)

    def insert(
        self,
        vectors: List[List[float]],
        payloads: Optional[List[Dict]] = None,
        ids: Optional[List[str]] = None,
        **kwargs
    ):
        """Insert vectors into collection."""
        if not self.collection:
            logger.warning("No collection initialized for insertion.")
            return

        total_count = len(vectors)
        if total_count == 0:
            return

        bm25_encoder = self._get_bm25_encoder()

        sparse_vectors = None
        if bm25_encoder is not None:
            has_sparse = False
            if hasattr(self.collection, "index") and hasattr(self.collection.index, "indexes"):
                has_sparse = any(isinstance(x, SparseIndex) for x in self.collection.index.indexes.values())
            
            if has_sparse:
                texts = [payload.get("data", "") for payload in payloads] if payloads else [""] * total_count
                try:
                    sparse_vectors = bm25_encoder.encode_texts(texts)
                except Exception as e:
                    logger.warning(f"Failed to encode texts to sparse vectors: {e}")

        docs = []
        for idx in range(total_count):
            metadata_dict = payloads[idx] if payloads and idx < len(payloads) else {}
            doc_id = ids[idx] if ids and idx < len(ids) else f"{time.time_ns()}-{hash(tuple(vectors[idx]))}-{idx}"
            
            doc_attrs = {
                "id": doc_id,
                "vector": vectors[idx],
                "text": metadata_dict.get("data", ""),
                "metadata": json.dumps(metadata_dict),
            }
            for key in ["user_id", "run_id", "agent_id", "hash"]:
                if metadata_dict.get(key) is not None:
                    doc_attrs[key] = metadata_dict[key]
            
            if sparse_vectors is not None and idx < len(sparse_vectors):
                doc_attrs["sparse_vector"] = sparse_vectors[idx]

            doc = Document(**doc_attrs)
            docs.append(doc)

        self.collection.upsert(docs)

    def search(
        self,
        query: str,
        vectors: List[float],
        top_k: int = 5,
        filters: Optional[Dict] = None,
        **kwargs
    ) -> List[OutputData]:
        """Search similar vectors."""
        if not self.collection:
            logger.warning("No collection initialized for search.")
            return []

        expr = None
        if filters:
            expr = self._dict_to_tencent_expr(filters)

        search_args = {
            "vectors": [vectors],
            "filter": Filter(expr) if expr else None,
            "params": SearchParams(ef=10),
            "retrieve_vector": False,
            "limit": top_k,
        }

        try:
            res = self.collection.search(**search_args)
            output = []
            if res and len(res) > 0:
                for match in res[0]:
                    doc_id = match.get("id")
                    score = match.get("score", 0.0)
                    
                    metadata = {}
                    raw_meta = match.get("metadata")
                    if raw_meta and isinstance(raw_meta, str):
                        try:
                            metadata = json.loads(raw_meta)
                        except Exception:
                            pass
                    else:
                        for field in ["user_id", "run_id", "agent_id", "hash"]:
                            if match.get(field) is not None:
                                metadata[field] = match.get(field)
                                
                    if "data" not in metadata and "text" in match:
                        metadata["data"] = match["text"]
                        
                    output.append(OutputData(
                        id=doc_id,
                        score=float(score),
                        payload=metadata
                    ))
            return output
        except Exception as e:
            logger.warning(f"Tencent vector search failed: {e}")
            return []

    def keyword_search(
        self,
        query: str,
        top_k: int = 5,
        filters: dict = None,
        **kwargs
    ) -> Optional[List[OutputData]]:
        """Perform keyword search via sparse vectors."""
        if not self.collection:
            logger.warning("No collection initialized for keyword search.")
            return None

        has_sparse = False
        if hasattr(self.collection, "index") and hasattr(self.collection.index, "indexes"):
            has_sparse = any(isinstance(x, SparseIndex) for x in self.collection.index.indexes.values())
        
        if not has_sparse:
            return None

        bm25 = self._get_bm25_encoder()
        if bm25 is None:
            return None
        try:
            sparse_vector = bm25.encode_queries(query)
        except Exception as e:
            logger.warning(f"Failed to encode query to sparse vector: {e}")
            return None

        expr = None
        if filters:
            expr = self._dict_to_tencent_expr(filters)

        try:
            res = self.collection.fulltext_search(
                data=sparse_vector,
                field_name="sparse_vector",
                filter=expr,
                limit=top_k,
                retrieve_vector=False,
            )
            
            output = []
            for doc in res:
                doc_id = doc.get("id")
                score = doc.get("score", 0.0)
                
                metadata = {}
                raw_meta = doc.get("metadata")
                if raw_meta and isinstance(raw_meta, str):
                    try:
                        metadata = json.loads(raw_meta)
                    except Exception:
                        pass
                else:
                    for field in ["user_id", "run_id", "agent_id", "hash"]:
                        if doc.get(field) is not None:
                            metadata[field] = doc.get(field)
                            
                if "data" not in metadata and "text" in doc:
                    metadata["data"] = doc["text"]
                    
                output.append(OutputData(
                    id=doc_id,
                    score=float(score),
                    payload=metadata
                ))
            return output
        except Exception as e:
            logger.warning(f"Tencent fulltext_search failed: {e}")
            return None

    def delete(self, vector_id: str):
        """Delete a vector by ID."""
        if not self.collection:
            return
        try:
            self.collection.delete(document_ids=[vector_id])
        except Exception as e:
            logger.warning(f"Failed to delete vector {vector_id}: {e}")

    def update(self, vector_id: str, vector: Optional[List[float]] = None, payload: Optional[Dict] = None):
        """Update a vector and its payload."""
        self.delete(vector_id)
        if vector is not None and payload is not None:
            self.insert([vector], [payload], [vector_id])

    def get(self, vector_id: str) -> Optional[OutputData]:
        """Retrieve a vector by ID."""
        if not self.collection:
            return None
        try:
            res = self.collection.query(
                document_ids=[vector_id],
                retrieve_vector=False,
            )
            if res and len(res) > 0:
                doc = res[0]
                metadata = {}
                raw_meta = doc.get("metadata")
                if raw_meta and isinstance(raw_meta, str):
                    try:
                        metadata = json.loads(raw_meta)
                    except Exception:
                        pass
                else:
                    for field in ["user_id", "run_id", "agent_id", "hash"]:
                        if doc.get(field) is not None:
                            metadata[field] = doc.get(field)
                if "data" not in metadata and "text" in doc:
                    metadata["data"] = doc["text"]
                return OutputData(
                    id=doc.get("id"),
                    score=None,
                    payload=metadata
                )
        except Exception as e:
            logger.warning(f"Failed to get vector {vector_id}: {e}")
        return None

    def list_cols(self) -> List[str]:
        """List all collections."""
        try:
            cols = self.db.list_collections()
            return [col.name for col in cols]
        except Exception as e:
            logger.warning(f"Failed to list collections: {e}")
            return [self.collection_name]

    def delete_col(self):
        """Delete the collection."""
        if not self.collection:
            return
        try:
            self.db.drop_collection(self.collection_name)
            self.collection = None
        except Exception as e:
            logger.warning(f"Failed to delete collection {self.collection_name}: {e}")

    def col_info(self) -> Dict[str, Any]:
        """Get collection info."""
        return {
            "name": self.collection_name,
            "embedding_model_dims": self.embedding_model_dims,
            "metric_type": self.metric_type,
        }

    def list(self, filters=None, top_k=None) -> List[OutputData]:
        """List all vectors matching filters."""
        if not self.collection:
            return []
        
        expr = None
        if filters:
            expr = self._dict_to_tencent_expr(filters)

        try:
            res = self.collection.query(
                filter=expr,
                limit=top_k,
                retrieve_vector=False,
            )
            output = []
            for doc in res:
                doc_id = doc.get("id")
                
                metadata = {}
                raw_meta = doc.get("metadata")
                if raw_meta and isinstance(raw_meta, str):
                    try:
                        metadata = json.loads(raw_meta)
                    except Exception:
                        pass
                else:
                    for field in ["user_id", "run_id", "agent_id", "hash"]:
                        if doc.get(field) is not None:
                            metadata[field] = doc.get(field)
                            
                if "data" not in metadata and "text" in doc:
                    metadata["data"] = doc["text"]
                    
                output.append(OutputData(
                    id=doc_id,
                    score=None,
                    payload=metadata
                ))
            return output
        except Exception as e:
            logger.warning(f"Failed to list: {e}")
            return []

    def reset(self):
        """Reset the collection by dropping and recreating it."""
        try:
            self.delete_col()
        except Exception:
            pass
        self.create_col(
            name=self.collection_name,
            vector_size=self.embedding_model_dims,
            distance=self.metric_type,
        )
