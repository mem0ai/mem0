import json
import logging

from mem0.vector_stores.base import VectorStoreBase
from typing import Any, Optional, Dict

import tablestore
from tablestore_for_agent_memory.knowledge.knowledge_store import KnowledgeStore
from tablestore_for_agent_memory.base.base_knowledge_store import Document
from tablestore_for_agent_memory.base.filter import Filters

logger = logging.getLogger(__name__)

class OutputData:
    def __init__(self, document: Document, score=None, metadata_name='payload'):
        self._metadata_name = metadata_name
        self.id: Optional[str] = document.document_id # memory id
        self.score: Optional[float] = score  # distance
        self.payload: Optional[Dict] = self._metadata2payload(document.metadata)  # metadata
        self.payload['data'] = document.text

    def _metadata2payload(self, metadata):
        return json.loads(metadata[f'{self._metadata_name}_source'])

metric_str2metric_type_dict = {
    "VM_EUCLIDEAN": tablestore.VectorMetricType.VM_EUCLIDEAN,
    "VM_COSINE": tablestore.VectorMetricType.VM_COSINE,
    "VM_DOT_PRODUCT": tablestore.VectorMetricType.VM_DOT_PRODUCT,
}

class AliyunTableStore(VectorStoreBase):
    def __init__(
            self,
            endpoint: str,
            instance_name: str,
            access_key_id: str,
            access_key_secret: str,
            vector_dimension: int,
            sts_token: Optional[str] = None,
            collection_name: str = "mem0",
            search_index_name: str = "mem0_search_index",
            text_field: str = "text",
            embedding_field: str = "embedding",
            vector_metric_type: str = "VM_COSINE",
            **kwargs: Any,
    ):
        self._tablestore_client = tablestore.OTSClient(
            end_point=endpoint,
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
            instance_name=instance_name,
            sts_token=None if sts_token == "" else sts_token,
            retry_policy=tablestore.WriteRetryPolicy(),
        )

        self._vector_dimension = vector_dimension
        self._collection_name = collection_name
        self._search_index_name = search_index_name
        self._metadata_name = 'payload'
        self._key_value_hyphen = '='
        self._search_index_schema = [
            tablestore.FieldSchema(
                self._metadata_name,
                tablestore.FieldType.KEYWORD,
                index=True,
                is_array=True,
                enable_sort_and_agg=True,
            ),
            tablestore.FieldSchema(
                f'{self._metadata_name}_source',
                tablestore.FieldType.KEYWORD,
                index=False,
                is_array=False,
                enable_sort_and_agg=False,
            )
        ]
        self._text_field = text_field
        self._embedding_field = embedding_field
        self._vector_metric_type = metric_str2metric_type_dict[vector_metric_type]

        self._knowledge_store = KnowledgeStore(
            tablestore_client=self._tablestore_client,
            vector_dimension=self._vector_dimension,
            enable_multi_tenant=False,
            table_name=self._collection_name,
            search_index_name=self._search_index_name,
            search_index_schema=self._search_index_schema,
            text_field=self._text_field,
            embedding_field=self._embedding_field,
            vector_metric_type=self._vector_metric_type,
            **kwargs,
        )

        self.create_col(**kwargs)

    def create_col(self, **kwargs: Any):
        """Create a new collection."""
        if self._collection_name in self.list_cols():
            logger.warning(f"tablestore table:[{self._collection_name}] already exists")
            return
        self._knowledge_store.init_table()

    def _payload2metadata(self, payload: Dict):
        payload_ = json.dumps([f'{key}{self._key_value_hyphen}{value}' for key, value in payload.items()], ensure_ascii=False)
        return {
            self._metadata_name: payload_,
            f'{self._metadata_name}_source': json.dumps(payload, ensure_ascii=False),
        }

    def insert(self, vectors: list, payloads: list = None, ids: list = None):
        """Insert vectors into a collection."""
        payloads_ = payloads if payloads is not None else []
        documents = []

        for id, vector, payload in zip(ids, vectors, payloads_):
            payload_ = payload.copy() if payload is not None else {}
            documents.append(
                Document(
                    document_id=id,
                    text=payload_.pop('data')
                    if 'data' in payload_.keys()
                    else None,
                    embedding=vector,
                    metadata=self._payload2metadata(payload_),
                )
            )

        for document in documents:
            self._knowledge_store.put_document(document)

    def _create_filter(self, filters: dict):
        """Create filters from dict (format of mem0 filters)"""
        if filters is None:
            return None

        if len(filters.keys()) == 1:
            meta_key, meta_value = tuple(filters.items())[0]
            return Filters.eq(self._metadata_name, f'{meta_key}{self._key_value_hyphen}{meta_value}')

        return Filters.logical_and(
            [
                Filters.eq(self._metadata_name, f'{meta_key}{self._key_value_hyphen}{meta_value}')
                for meta_key, meta_value in filters.items()
            ]
        )

    def search(self, query, vectors, limit=5, filters=None):
        """Search for similar vectors."""
        response = self._knowledge_store.vector_search(
            query_vector=vectors,
            top_k=limit,
            metadata_filter=self._create_filter(filters),
        )
        return [
            OutputData(
                document=hit.document,
                score=hit.score,
                metadata_name=self._metadata_name,
            )
            for hit in response.hits
        ]

    def delete(self, vector_id):
        """Delete a vector by ID."""
        self._knowledge_store.delete_document(document_id=vector_id)

    def update(self, vector_id, vector=None, payload=None):
        """Update a vector and its payload."""
        payload_ = payload.copy() if payload is not None else {}
        document_for_update = Document(
            document_id=vector_id,
            text=payload_.pop('data')
                 if 'data' in payload_.keys()
                 else None,
            embedding=vector,
            metadata=self._payload2metadata(payload_),
        )
        self._knowledge_store.update_document(document_for_update)

    def get(self, vector_id):
        """Retrieve a vector by ID."""
        document = self._knowledge_store.get_document(document_id=vector_id)
        return OutputData(
            document=document,
            metadata_name=self._metadata_name,
        )

    def list_cols(self):
        """List all collections."""
        return self._tablestore_client.list_table()

    def delete_col(self):
        """Delete a collection."""
        self._tablestore_client.delete_search_index(table_name=self._collection_name, index_name=self._search_index_name)
        self._tablestore_client.delete_table(table_name=self._collection_name)

    def col_info(self):
        """Get information about a collection."""
        self._tablestore_client.describe_table(table_name=self._collection_name)

    def list(self, filters=None, limit=100):
        """List all memories."""
        return [
            [
                OutputData(
                    document=hit.document,
                    metadata_name=self._metadata_name,
                )
                for hit in self._knowledge_store.search_documents(metadata_filter=self._create_filter(filters), limit=limit).hits
            ]
        ]

    def reset(self):
        """Reset by delete the collection and recreate it."""
        logger.warning(f"Resetting table {self._collection_name}...")
        self.delete_col()
        self.create_col()