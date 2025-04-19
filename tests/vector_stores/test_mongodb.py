import time
import pytest
from unittest.mock import MagicMock, patch
from mem0.vector_stores.mongodb import MongoVector
from pymongo.operations import SearchIndexModel

@pytest.fixture
@patch("mem0.vector_stores.mongodb.MongoClient")
def mongo_vector_fixture(mock_mongo_client):
    mock_client = mock_mongo_client.return_value
    mock_db = mock_client["test_db"]
    mock_collection = mock_db["test_collection"]
    mock_collection.list_search_indexes.return_value = []
    mock_collection.aggregate.return_value = []
    mock_collection.find_one.return_value = None
    mock_collection.find.return_value = []
    mock_db.list_collection_names.return_value = []

    mongo_vector = MongoVector(
        db_name="test_db",
        collection_name="test_collection",
        embedding_model_dims=1536,
        user="username",
        password="password",
    )
    return mongo_vector, mock_collection, mock_db

def test_initalize_create_col(mongo_vector_fixture):
    mongo_vector, mock_collection, mock_db = mongo_vector_fixture
    assert mongo_vector.collection_name == "test_collection"
    assert mongo_vector.embedding_model_dims == 1536
    assert mongo_vector.db_name == "test_db"

    # Verify create_col being called
    mock_db.list_collection_names.assert_called_once()
    mock_collection.insert_one.assert_called_once_with({"_id": 0, "placeholder": True})
    mock_collection.delete_one.assert_called_once_with({"_id": 0})
    assert mongo_vector.index_name == "test_collection_vector_index"
    mock_collection.list_search_indexes.assert_called_once_with(name="test_collection_vector_index")
    mock_collection.create_search_index.assert_called_once()
    args, _ = mock_collection.create_search_index.call_args
    search_index_model = args[0].document
    assert search_index_model == {
        "name": "test_collection_vector_index",
        "definition": {
            "mappings": {
                "dynamic": False,
                "fields": {
                    "embedding": {
                        "type": "knnVector",
                        "d": 1536,
                        "similarity": "cosine",
                    }
                }
            }
        }
    }
    assert mongo_vector.collection == mock_collection

def test_insert(mongo_vector_fixture):
    mongo_vector, mock_collection, _ = mongo_vector_fixture
    vectors = [[0.1] * 1536, [0.2] * 1536]
    payloads = [{"name": "vector1"}, {"name": "vector2"}]
    ids = ["id1", "id2"]

    mongo_vector.insert(vectors, payloads, ids)
    expected_records=[
        ({"_id": ids[0], "embedding": vectors[0], "payload": payloads[0]}),
        ({"_id": ids[1], "embedding": vectors[1], "payload": payloads[1]})
    ]
    mock_collection.insert_many.assert_called_once_with(expected_records)

def test_search(mongo_vector_fixture):
    mongo_vector, mock_collection, _ = mongo_vector_fixture
    query_vector = [0.1] * 1536
    mock_collection.aggregate.return_value = [
        {"_id": "id1", "score": 0.9, "payload": {"key": "value1"}},
        {"_id": "id2", "score": 0.8, "payload": {"key": "value2"}},
    ]
    mock_collection.list_search_indexes.return_value = ["test_collection_vector_index"]

    results = mongo_vector.search("query_str", query_vector, limit=2)
    mock_collection.list_search_indexes.assert_called_with(name="test_collection_vector_index")
    mock_collection.aggregate.assert_called_once_with([
        {
            "$vectorSearch": {
                "index": "test_collection_vector_index",
                "limit": 2,
                "numCandidates": 2,
                "queryVector": query_vector,
                "path": "embedding",
            },
        },
        {"$set": {"score": {"$meta": "vectorSearchScore"}}},
        {"$project": {"embedding": 0}},
    ])
    assert len(results) == 2
    assert results[0].id == "id1"
    assert results[0].score == 0.9
    assert results[1].id == "id2"
    assert results[1].score == 0.8

def test_delete(mongo_vector_fixture):
    mongo_vector, mock_collection, _ = mongo_vector_fixture
    mock_delete_result = MagicMock()
    mock_delete_result.deleted_count = 1
    mock_collection.delete_one.return_value = mock_delete_result

    mongo_vector.delete("id1")
    mock_collection.delete_one.assert_called_with({"_id": "id1"})

def test_update(mongo_vector_fixture):
    mongo_vector, mock_collection, _ = mongo_vector_fixture
    mock_update_result = MagicMock()
    mock_update_result.matched_count = 1
    mock_collection.update_one.return_value = mock_update_result
    idValue = "id1"
    vectorValue = [0.2] * 1536
    payloadValue = {"key": "updated"}

    mongo_vector.update(idValue, vector=vectorValue, payload=payloadValue)
    mock_collection.update_one.assert_called_once_with(
        {"_id": idValue},
        {"$set": {"embedding": vectorValue, "payload": payloadValue}},
    )

def test_get(mongo_vector_fixture):
    mongo_vector, mock_collection, _ = mongo_vector_fixture
    mock_collection.find_one.return_value = {"_id": "id1", "payload": {"key": "value1"}}

    result = mongo_vector.get("id1")
    assert result is not None
    assert result.id == "id1"
    assert result.payload == {"key": "value1"}

def test_list_cols(mongo_vector_fixture):
    mongo_vector, _, mock_db = mongo_vector_fixture
    mock_db.list_collection_names.return_value = ["col1", "col2"]

    collections = mongo_vector.list_cols()
    assert collections == ["col1", "col2"]

def test_delete_col(mongo_vector_fixture):
    mongo_vector, mock_collection, _ = mongo_vector_fixture

    mongo_vector.delete_col()
    mock_collection.drop.assert_called_once()

def test_col_info(mongo_vector_fixture):
    mongo_vector, _, mock_db = mongo_vector_fixture
    mock_db.command.return_value = {"count": 10, "size": 1024}

    info = mongo_vector.col_info()
    mock_db.command.assert_called_once_with("collstats", "test_collection")
    assert info["name"] == "test_collection"
    assert info["count"] == 10
    assert info["size"] == 1024

def test_list(mongo_vector_fixture):
    mongo_vector, mock_collection, _ = mongo_vector_fixture
    mock_cursor = MagicMock()
    mock_cursor.limit.return_value = [
        {"_id": "id1", "payload": {"key": "value1"}},
        {"_id": "id2", "payload": {"key": "value2"}},
    ]
    mock_collection.find.return_value = mock_cursor

    query_filters = {"_id": {"$in": ["id1", "id2"]}}
    results = mongo_vector.list(filters=query_filters, limit=2)
    mock_collection.find.assert_called_once_with(query_filters)
    mock_cursor.limit.assert_called_once_with(2)
    assert len(results) == 2
    assert results[0].id == "id1"
    assert results[0].payload == {"key": "value1"}
    assert results[1].id == "id2"
    assert results[1].payload == {"key": "value2"}
