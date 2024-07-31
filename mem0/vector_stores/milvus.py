import logging
from typing import List, Dict

from pymilvus import MilvusClient, DataType
from mem0.vector_stores.base import VectorStoreBase


class Milvus(VectorStoreBase):
    def __init__(
        self,
        uri: str,
        token: str = None
    ):
        self.client = MilvusClient(
            uri=uri,
            token=token
        )

    def create_col(self, name, vector_size, distance="COSINE"):
        if self.client.has_collection(collection_name=name):
            logging.debug(f"Collection {name} already exists. Drop the old collection.")
            self.client.drop_collection(collection_name=name)

        schema = self.client.create_schema(
            auto_id=False,
            enable_dynamic_field=True,
        )
        schema.add_field(field_name="id", datatype=DataType.VARCHAR, max_length=36, is_primary=True)
        schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=vector_size)

        index_params = self.client.prepare_index_params()
        index_params.add_index(field_name="vector", index_type="AUTOINDEX", metric_type=distance)

        self.client.create_collection(
            collection_name=name,
            schema=schema,
            index_params=index_params
        )

    def insert(self, name, vectors, payloads=None, ids=None):
        data = dict()

        for idx, vector in enumerate(vectors):
            data['id'] = str(idx) if ids is None else ids[idx]
            data['vector'] = vector
            data['payload'] = payloads[idx] if payloads else None

        self.client.upsert(
            collection_name=name,
            data=data
        )

    def _generate_milvus_filter(self, filters: dict[str, str]):
        operands = []
        for key, value in filters.items():
            if isinstance(value, str):
                operands.append(f'(payload["{key}"] == "{value}")')
            else:
                operands.append(f'(payload["{key}"] == {value})')

        return " and ".join(operands)

    def search(self, name, query, limit=5, filters=None):
        if filters:
            filter_expression = self._generate_milvus_filter(filters)
        else:
            filter_expression = None

        hits = self.client.search(
            collection_name=name,
            data=[query],
            filter=filter_expression,
            limit=limit
        )

        return hits[0]

    def delete(self, name, vector_id):
        self.client.delete(
            collection_name=name,
            ids=vector_id,
        )

    def update(self, name, vector_id, vector=None, payload=None):
        data = dict()

        data['id'] = vector_id
        data['vector'] = vector
        data['payload'] = payload

        self.client.upsert(
            collection_name=name,
            data=data
        )

    def get(self, name, vector_id):
        result = self.client.get(
            collection_name=name,
            ids=vector_id
        )

        return result[0] if result else None

    def list_cols(self) -> List[str]:
        return self.client.list_collections()

    def delete_col(self, name):
        self.client.drop_collection(collection_name=name)

    def col_info(self, name) -> Dict:
        return self.client.get_collection_stats(collection_name=name)

    def list(self, name, filters=None, limit=100):
        if filters:
            filter_expression = self._generate_milvus_filter(filters)

            result = self.client.query(
                collection_name=name,
                filter=filter_expression,
                limit=limit
            )
            return [result]
        else:
            return None
