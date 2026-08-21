import json
import logging
import time
from typing import Dict, List, Optional

from pydantic import BaseModel

from mem0.vector_stores.base import VectorStoreBase

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    raise ImportError("The 'boto3' library is required. Please install it using 'pip install boto3'.")

logger = logging.getLogger(__name__)

# Attributes mem0 filters on; declared as inline filters in the vector index
# search schema so SearchVectors can constrain on them server-side.
FILTERABLE_ATTRIBUTES = ("user_id", "agent_id", "run_id")

VECTOR_INDEX_NAME = "mem0-vector-index"

DISTANCE_FUNCTIONS = {
    "cosine": "COSINE",
    "euclidean": "EUCLIDEAN",
}


class OutputData(BaseModel):
    id: Optional[str]
    score: Optional[float]
    payload: Optional[Dict]


class DynamoDB(VectorStoreBase):
    def __init__(
        self,
        collection_name: str,
        embedding_model_dims: int,
        distance_metric: str = "cosine",
        region_name: Optional[str] = None,
        endpoint_url: Optional[str] = None,
    ):
        self.client = boto3.client("dynamodb", region_name=region_name, endpoint_url=endpoint_url)
        if not hasattr(self.client, "search_vectors"):
            raise RuntimeError(
                "This botocore release does not support DynamoDB vector search. "
                "Upgrade with 'pip install \"boto3>=1.43.64\"'."
            )
        self.collection_name = collection_name
        self.embedding_model_dims = embedding_model_dims
        self.distance_metric = distance_metric

        self.create_col(self.collection_name, self.embedding_model_dims, self.distance_metric)

    def _table_exists(self, name) -> bool:
        try:
            self.client.describe_table(TableName=name)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                return False
            raise

    def create_col(self, name, vector_size, distance="cosine"):
        if distance not in DISTANCE_FUNCTIONS:
            raise ValueError(f"Unsupported distance metric '{distance}'. Options: {sorted(DISTANCE_FUNCTIONS)}")
        if self._table_exists(name):
            logger.info(f"Table '{name}' already exists.")
            return
        logger.info(f"Creating table '{name}' with vector index.")
        # Attributes referenced by the search schema must be declared in
        # AttributeDefinitions, in addition to the key attribute.
        attribute_definitions = [{"AttributeName": "id", "AttributeType": "S"}] + [
            {"AttributeName": attr, "AttributeType": "S"} for attr in FILTERABLE_ATTRIBUTES
        ]
        self.client.create_table(
            TableName=name,
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=attribute_definitions,
            BillingMode="PAY_PER_REQUEST",
            VectorIndexes=[
                {
                    "IndexName": VECTOR_INDEX_NAME,
                    "VectorAttribute": {"AttributeName": "vector"},
                    "SearchSchema": [
                        {"AttributeName": attr, "SearchSchemaElementType": "INLINE_FILTER"}
                        for attr in FILTERABLE_ATTRIBUTES
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                    "Dimensions": vector_size,
                    "DistanceFunction": DISTANCE_FUNCTIONS[distance],
                }
            ],
        )
        self.client.get_waiter("table_exists").wait(TableName=name)

    def _to_item(self, vector_id, vector, payload) -> Dict:
        payload = payload or {}
        item = {
            "id": {"S": str(vector_id)},
            "vector": {"L": [{"N": str(x)} for x in vector]},
            "payload": {"S": json.dumps(payload)},
        }
        for attr in FILTERABLE_ATTRIBUTES:
            value = payload.get(attr)
            if value is not None:
                item[attr] = {"S": str(value)}
        return item

    def _parse_item(self, item: Dict, distance: Optional[float] = None) -> OutputData:
        payload = json.loads(item.get("payload", {}).get("S", "{}"))
        score = None
        if distance is not None:
            if self.distance_metric == "cosine":
                score = max(0.0, 1.0 - distance)
            else:  # euclidean
                score = 1.0 / (1.0 + distance)
        return OutputData(id=item["id"]["S"], score=score, payload=payload)

    def insert(self, vectors, payloads=None, ids=None):
        requests = [
            {"PutRequest": {"Item": self._to_item(ids[i], vec, payloads[i] if payloads else {})}}
            for i, vec in enumerate(vectors)
        ]
        for start in range(0, len(requests), 25):
            response = self.client.batch_write_item(RequestItems={self.collection_name: requests[start : start + 25]})
            while response.get("UnprocessedItems"):
                response = self.client.batch_write_item(RequestItems=response["UnprocessedItems"])

    def _build_condition(self, filters: Optional[Dict]):
        """Split filters into a server-side search condition and a client-side remainder."""
        if not filters:
            return None, {}
        server = {k: v for k, v in filters.items() if k in FILTERABLE_ATTRIBUTES and v is not None}
        remainder = {k: v for k, v in filters.items() if k not in server}
        if not server:
            return None, remainder
        names = {f"#f{i}": k for i, k in enumerate(server)}
        values = {f":v{i}": {"S": str(v)} for i, v in enumerate(server.values())}
        expression = " AND ".join(f"#f{i} = :v{i}" for i in range(len(server)))
        return {
            "SearchConditionExpression": expression,
            "ExpressionAttributeNames": names,
            "ExpressionAttributeValues": values,
        }, remainder

    def search(self, query, vectors, top_k=5, filters=None):
        condition, remainder = self._build_condition(filters)
        params = {
            "TableName": self.collection_name,
            "IndexName": VECTOR_INDEX_NAME,
            "SearchVector": [{"N": str(x)} for x in vectors],
            "TopK": top_k,
        }
        if condition:
            params.update(condition)
        response = self.client.search_vectors(**params)
        results = [self._parse_item(r["Item"], r.get("Score")) for r in response.get("SearchResults", [])]
        if remainder:
            results = [
                r for r in results if r.payload and all(r.payload.get(k) == v for k, v in remainder.items())
            ]
        return results

    def delete(self, vector_id):
        self.client.delete_item(TableName=self.collection_name, Key={"id": {"S": str(vector_id)}})

    def update(self, vector_id, vector=None, payload=None):
        sets, names, values = [], {}, {}
        if vector is not None:
            sets.append("#vec = :vec")
            names["#vec"] = "vector"
            values[":vec"] = {"L": [{"N": str(x)} for x in vector]}
        if payload is not None:
            sets.append("#pl = :pl")
            names["#pl"] = "payload"
            values[":pl"] = {"S": json.dumps(payload)}
            for i, attr in enumerate(FILTERABLE_ATTRIBUTES):
                value = payload.get(attr)
                if value is not None:
                    sets.append(f"#a{i} = :a{i}")
                    names[f"#a{i}"] = attr
                    values[f":a{i}"] = {"S": str(value)}
        if not sets:
            return
        self.client.update_item(
            TableName=self.collection_name,
            Key={"id": {"S": str(vector_id)}},
            UpdateExpression="SET " + ", ".join(sets),
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
        )

    def get(self, vector_id) -> Optional[OutputData]:
        response = self.client.get_item(TableName=self.collection_name, Key={"id": {"S": str(vector_id)}})
        item = response.get("Item")
        if not item:
            return None
        return self._parse_item(item)

    def list_cols(self):
        tables = []
        paginator = self.client.get_paginator("list_tables")
        for page in paginator.paginate():
            tables.extend(page.get("TableNames", []))
        return tables

    def delete_col(self):
        self.client.delete_table(TableName=self.collection_name)
        self.client.get_waiter("table_not_exists").wait(TableName=self.collection_name)

    def col_info(self):
        return self.client.describe_table(TableName=self.collection_name)["Table"]

    def list(self, filters=None, top_k=None):
        params = {"TableName": self.collection_name}
        condition, remainder = self._build_condition(filters)
        if condition:
            params["FilterExpression"] = condition["SearchConditionExpression"]
            params["ExpressionAttributeNames"] = condition["ExpressionAttributeNames"]
            params["ExpressionAttributeValues"] = condition["ExpressionAttributeValues"]
        items = []
        paginator = self.client.get_paginator("scan")
        for page in paginator.paginate(**params):
            items.extend(page.get("Items", []))
        results = [self._parse_item(item) for item in items]
        if remainder:
            results = [
                r for r in results if r.payload and all(r.payload.get(k) == v for k, v in remainder.items())
            ]
        if top_k:
            results = results[:top_k]
        return [results]

    def reset(self):
        logger.warning(f"Resetting table {self.collection_name}...")
        self.delete_col()
        self.create_col(self.collection_name, self.embedding_model_dims, self.distance_metric)
