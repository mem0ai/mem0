from abc import ABC, abstractmethod
import logging
from typing import Any, Dict, List, Literal, Optional, Union
import uuid

from pydantic import BaseModel

try:
    from elasticsearch import Elasticsearch
    from elasticsearch.helpers import BulkIndexError, bulk
except ImportError:
    raise ImportError(
        "The 'Elasticsearch' library is required. Please install it using 'pip install elasticsearch'."
    )

from mem0.configs.vector_stores.esvector import (
    BaseRetrievalStrategy,
    DistanceStrategy,
    ESVectorConfig,
)
from mem0.vector_stores.base import VectorStoreBase


logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: Optional[str]  # memory id
    score: Optional[float]  # distance
    payload: Optional[Dict]  # metadata


class ESVector(VectorStoreBase):
    def __init__(
        self,
        collection_name: str,
        client: Optional[Elasticsearch] = None,
        endpoint: Optional[str] = None,
        api_key: Optional[int] = None,
        vector_query_field: Optional[str] = "vector",
        query_field: Optional[str] = "text",
        distance_strategy: Optional[
            Literal[
                DistanceStrategy.COSINE,
                DistanceStrategy.DOT_PRODUCT,
                DistanceStrategy.EUCLIDEAN_DISTANCE,
                DistanceStrategy.MAX_INNER_PRODUCT,
            ]
        ] = None,
        strategy: BaseRetrievalStrategy = ESVectorConfig.ApproxRetrievalStrategy(),
    ):
        if client:
            self.client = client
        else:
            self.client = Elasticsearch(
                endpoint,
                api_key=api_key,
            )
        self.index_name = collection_name
        self.query_field = query_field
        self.vector_query_field = vector_query_field
        self.distance_strategy = (
            DistanceStrategy.COSINE
            if distance_strategy is None
            else DistanceStrategy[distance_strategy]
        )
        self.strategy = strategy


    def _parse_output(self, hit: Dict) -> List[OutputData]:
        payload = hit["_source"].get("metadata", {})
        payload["data"] = hit["_source"].get(self.query_field, "")
        return OutputData(
            id=hit["_id"],
            score=hit.get("_score", None),
            payload=payload,
        )


    def create_col(
        self,
        name: str,
        vector_size: Optional[int] = None,
    ) -> None:
        if self.client.indices.exists(index=name).body:
            logging.info(f"Index {name} already exists. Skipping creation.")

        else:
            if vector_size is None and self.strategy.require_inference():
                raise ValueError(
                    "Cannot create index without specifying dims_length "
                    "when the index doesn't already exist. We infer "
                    "dims_length from the first embedding. Check that "
                    "you have provided an embedding function."
                )

            self.strategy.before_index_setup(
                client=self.client,
                text_field=self.query_field,
                vector_query_field=self.vector_query_field,
            )

            indexSettings = self.strategy.index(
                vector_query_field=self.vector_query_field,
                text_field=self.query_field,
                dims_length=vector_size,
                similarity=self.distance_strategy,
            )

            logger.info(
                f"Creating index {name} with mappings {indexSettings['mappings']}"
            )

            self.client.indices.create(index=name, **indexSettings)


    def insert(
        self,
        vectors: list[List[float]],
        payloads: Optional[List[Dict[Any, Any]]] = None,
        ids: Optional[list[str]] = None,
        refresh_indices: bool = True,
        create_index_if_not_exists: bool = True,
        bulk_kwargs: Optional[Dict] = None,
    ):
        logger.info(f"Inserting {len(vectors)} vectors into index {self.index_name}")

        bulk_kwargs = bulk_kwargs or {}
        ids = ids or [str(uuid.uuid4()) for _ in vectors]
        requests = []

        if create_index_if_not_exists:
            self.create_col(self.index_name, len(vectors[0]))

        for i, vector in enumerate(vectors):
            metadata = payloads[i] if payloads else {}
            query_text = metadata.pop("data")

            requests.append(
                {
                    "_op_type": "index",
                    "_index": self.index_name,
                    self.vector_query_field: vector,
                    self.query_field: query_text,
                    "metadata": metadata,
                    "_id": ids[i],
                }
            )

            if len(requests) > 0:
                try:
                    success, failed = bulk(
                        self.client,
                        requests,
                        stats_only=True,
                        refresh=refresh_indices,
                        **bulk_kwargs,
                    )
                    logger.info(
                        f"Added {success} and failed to add {failed} vectors to index"
                    )

                    logger.info(f"added vectors {ids} to index")
                    return ids
                except BulkIndexError as e:
                    logger.error(f"Error adding vectors: {e}")
                    firstError = e.errors[0].get("index", {}).get("error", {})
                    logger.error(f"First error reason: {firstError.get('reason')}")
                    raise e
            else:
                logger.info("No texts to add to index")
                return []


    def search(
        self,
        query: List[float],
        limit: int = 4,
        filters: Optional[dict] = None,
        fetch_k: int = 50,
    ):
        self.create_col(self.index_name, len(query))

        fields = [
            "metadata",
            "_id",
            self.query_field,
        ]

        query_body = self.strategy.query(
            query_vector=query,
            query=None,
            k=limit,
            fetch_k=fetch_k if fetch_k > limit else limit,
            vector_query_field=self.vector_query_field,
            text_field=self.query_field,
            filter=self._parse_filters(filters or {}),
            similarity=self.distance_strategy,
        )

        logger.info(f"Query body: {query_body}")

        response = self.client.search(
            index=self.index_name,
            **query_body,
            size=limit,
            source=True,
            source_includes=fields,
        )

        logger.info(f"Search response: {response}")

        search_res = [self._parse_output(hit) for hit in response["hits"]["hits"]]

        return search_res


    def _parse_filters(self, filters: dict) -> list[dict]:
        _filters = []

        for key in filters:
            _filters.append({
                'term': {
                        f"metadata.{key}.keyword": {
                            'value': filters[key]
                        }
                }
            })
        
        return _filters


    def delete(
        self,
        vector_id: str,
        refresh_indices: Optional[bool] = True,
    ):
        body = []
        body.append({"_op_type": "delete", "_index": self.index_name, "_id": vector_id})

        try:
            bulk(self.client, body, refresh=refresh_indices, ignore_status=404)
            logger.info(f"Deleted {len(body)} texts from index")

            return True
        except BulkIndexError as e:
            logger.error(f"Error deleting texts: {e}")
            firstError = e.errors[0].get("index", {}).get("error", {})
            logger.error(f"First error reason: {firstError.get('reason')}")
            raise e


    def update(
        self,
        vector_id: str,
        vector: Optional[list[float]] = None,
        payload: Optional[Dict] = None,
    ):
        doc = {
            "doc": {
                self.vector_query_field: vector,
                self.query_field: payload.pop("data"),
                "metadata": payload,
            }
        }
        logger.info(
            f"Update vector with ID {vector_id} with vector{vector=} with payload {payload=}."
        )
        result = self.client.update(
            index=self.index_name,
            id=vector_id,
            body=doc,
        )
        if result["result"] != "updated":
            raise ValueError(
                f"Update vector with ID {vector_id} with {payload=} error."
            )
        logger.info(
            f"Update vector with ID {vector_id} with vector{vector=} with payload {payload=} success."
        )


    def get(self, vector_id: str):
        logger.info(f"Get vector with ID {vector_id}.")
        result = self.client.get(
            index=self.index_name,
            id=vector_id,
        )
        logger.info(f"Get response: {result}")
        return self._parse_output(result)


    def list_cols(self):
        raise NotImplementedError


    def delete_col(self):
        if not self.client.indices.exists(index=self.index_name):
            logging.info(f"Index {self.index_name} doesn't exist. Skipping deletion.")
            return

        response = self.client.indices.delete(index=self.index_name)

        if not response.get("acknowledged", False):
            raise ValueError(f"Delete index with name {self.index_name} failed.")

    def col_info(self):
        response = self.client.indices.get(
            index=self.index_name,
            ignore_unavailable=True,
        )
        return response.get("_source", {})
