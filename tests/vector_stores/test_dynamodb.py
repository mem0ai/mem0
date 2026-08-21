import json

import pytest

from mem0.configs.vector_stores.dynamodb import DynamoDBConfig
from mem0.vector_stores.dynamodb import DynamoDB

TABLE_NAME = "test-memories"
EMBEDDING_DIMS = 1536
REGION = "us-east-1"


@pytest.fixture
def mock_boto_client(mocker):
    """Fixture to mock the boto3 DynamoDB client."""
    mock_client = mocker.MagicMock()
    mocker.patch("boto3.client", return_value=mock_client)
    # Table does not exist yet -> create path
    mock_client.describe_table.side_effect = _resource_not_found
    return mock_client


def _resource_not_found(*args, **kwargs):
    from botocore.exceptions import ClientError

    raise ClientError({"Error": {"Code": "ResourceNotFoundException"}}, "DescribeTable")


@pytest.fixture
def store(mock_boto_client):
    s = DynamoDB(collection_name=TABLE_NAME, embedding_model_dims=EMBEDDING_DIMS, region_name=REGION)
    mock_boto_client.describe_table.side_effect = None
    return s


def test_initialization_creates_table_with_vector_index(mock_boto_client, store):
    call = mock_boto_client.create_table.call_args.kwargs
    assert call["TableName"] == TABLE_NAME
    vi = call["VectorIndexes"][0]
    assert vi["VectorAttribute"] == {"AttributeName": "vector"}
    assert vi["Dimensions"] == EMBEDDING_DIMS
    assert vi["DistanceFunction"] == "COSINE"
    # Search schema attributes must also be declared in AttributeDefinitions
    schema_attrs = {e["AttributeName"] for e in vi["SearchSchema"]}
    defined_attrs = {d["AttributeName"] for d in call["AttributeDefinitions"]}
    assert schema_attrs == {"user_id", "agent_id", "run_id"}
    assert schema_attrs <= defined_attrs


def test_unsupported_distance_metric_rejected(mock_boto_client):
    with pytest.raises(ValueError, match="Unsupported distance metric"):
        DynamoDB(
            collection_name=TABLE_NAME,
            embedding_model_dims=EMBEDDING_DIMS,
            distance_metric="hamming",
            region_name=REGION,
        )


def test_insert_serializes_vector_and_payload(mock_boto_client, store):
    mock_boto_client.batch_write_item.return_value = {}
    store.insert(vectors=[[0.1, 0.2]], payloads=[{"data": "alpha", "user_id": "u1"}], ids=["m1"])
    request = mock_boto_client.batch_write_item.call_args.kwargs["RequestItems"][TABLE_NAME][0]
    item = request["PutRequest"]["Item"]
    assert item["id"] == {"S": "m1"}
    assert item["vector"] == {"L": [{"N": "0.1"}, {"N": "0.2"}]}
    assert json.loads(item["payload"]["S"]) == {"data": "alpha", "user_id": "u1"}
    assert item["user_id"] == {"S": "u1"}  # promoted for server-side filtering


def test_insert_retries_unprocessed_items(mock_boto_client, store):
    retry_batch = {TABLE_NAME: [{"PutRequest": {"Item": {"id": {"S": "m1"}}}}]}
    mock_boto_client.batch_write_item.side_effect = [{"UnprocessedItems": retry_batch}, {}]
    store.insert(vectors=[[0.1]], payloads=[{}], ids=["m1"])
    assert mock_boto_client.batch_write_item.call_count == 2
    assert mock_boto_client.batch_write_item.call_args.kwargs["RequestItems"] == retry_batch


def test_search_converts_distance_to_similarity(mock_boto_client, store):
    mock_boto_client.search_vectors.return_value = {
        "SearchResults": [
            {"Item": {"id": {"S": "m1"}, "payload": {"S": "{}"}}, "Score": 0.0},
            {"Item": {"id": {"S": "m2"}, "payload": {"S": "{}"}}, "Score": 1.0},
        ]
    }
    results = store.search("q", [0.1] * EMBEDDING_DIMS, top_k=2)
    # Base contract: higher score = more similar. Cosine distance 0.0 -> 1.0
    assert results[0].score == 1.0
    assert results[1].score == 0.0


def test_search_builds_server_side_condition(mock_boto_client, store):
    mock_boto_client.search_vectors.return_value = {"SearchResults": []}
    store.search("q", [0.1], top_k=5, filters={"user_id": "u1", "agent_id": "a1"})
    call = mock_boto_client.search_vectors.call_args.kwargs
    assert "SearchConditionExpression" in call
    assert set(call["ExpressionAttributeNames"].values()) == {"user_id", "agent_id"}
    assert {v["S"] for v in call["ExpressionAttributeValues"].values()} == {"u1", "a1"}


def test_search_applies_remainder_filter_client_side(mock_boto_client, store):
    mock_boto_client.search_vectors.return_value = {
        "SearchResults": [
            {"Item": {"id": {"S": "m1"}, "payload": {"S": json.dumps({"topic": "x"})}}, "Score": 0.0},
            {"Item": {"id": {"S": "m2"}, "payload": {"S": json.dumps({"topic": "y"})}}, "Score": 0.1},
        ]
    }
    results = store.search("q", [0.1], top_k=5, filters={"topic": "x"})
    assert [r.id for r in results] == ["m1"]
    # Non-schema filter must not reach the service
    assert "SearchConditionExpression" not in mock_boto_client.search_vectors.call_args.kwargs


def test_get_returns_none_for_missing(mock_boto_client, store):
    mock_boto_client.get_item.return_value = {}
    assert store.get("missing") is None


def test_update_payload_promotes_filterable_attributes(mock_boto_client, store):
    store.update("m1", payload={"data": "new", "user_id": "u9"})
    call = mock_boto_client.update_item.call_args.kwargs
    assert "user_id" in call["ExpressionAttributeNames"].values()
    assert {"S": "u9"} in call["ExpressionAttributeValues"].values()


def test_reset_deletes_and_recreates(mock_boto_client, store):
    mock_boto_client.describe_table.side_effect = _resource_not_found
    store.reset()
    mock_boto_client.delete_table.assert_called_once_with(TableName=TABLE_NAME)
    assert mock_boto_client.create_table.call_count == 2  # init + reset


def test_config_rejects_extra_fields():
    with pytest.raises(ValueError, match="Extra fields not allowed"):
        DynamoDBConfig(collection_name="x", not_a_field=1)


def test_config_defaults():
    config = DynamoDBConfig()
    assert config.collection_name == "mem0"
    assert config.embedding_model_dims == 1536
    assert config.distance_metric == "cosine"
    assert config.endpoint_url is None
