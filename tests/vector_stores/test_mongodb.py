from unittest.mock import MagicMock, patch

import pytest

from mem0.vector_stores.mongodb import MongoDB


@pytest.fixture
@patch("mem0.vector_stores.mongodb.MongoClient")
def mongo_vector_fixture(mock_mongo_client):
    mock_client = mock_mongo_client.return_value
    mock_db = mock_client["test_db"]
    mock_collection = mock_db["test_collection"]
    mock_collection.list_search_indexes.return_value = []
    mock_collection.aggregate.return_value = []
    mock_collection.find_one.return_value = None
    
    # Create a proper mock cursor
    mock_cursor = MagicMock()
    mock_cursor.limit.return_value = mock_cursor
    mock_collection.find.return_value = mock_cursor
    
    mock_db.list_collection_names.return_value = []

    mongo_vector = MongoDB(
        db_name="test_db",
        collection_name="test_collection",
        embedding_model_dims=1536,
        mongo_uri="mongodb://username:password@localhost:27017",
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
                        "dimensions": 1536,
                        "similarity": "cosine",
                    }
                },
            }
        },
    }
    assert mongo_vector.collection == mock_collection


def test_insert(mongo_vector_fixture):
    mongo_vector, mock_collection, _ = mongo_vector_fixture
    vectors = [[0.1] * 1536, [0.2] * 1536]
    payloads = [{"name": "vector1"}, {"name": "vector2"}]
    ids = ["id1", "id2"]

    mongo_vector.insert(vectors, payloads, ids)
    expected_records = [
        ({"_id": ids[0], "embedding": vectors[0], "payload": payloads[0]}),
        ({"_id": ids[1], "embedding": vectors[1], "payload": payloads[1]}),
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
    mock_collection.aggregate.assert_called_once_with(
        [
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
        ]
    )
    assert len(results) == 2
    assert results[0].id == "id1"
    assert results[0].score == 0.9
    assert results[0].payload == {"key": "value1"}


def test_search_with_filters(mongo_vector_fixture):
    """Test search with agent_id and run_id filters."""
    mongo_vector, mock_collection, _ = mongo_vector_fixture
    query_vector = [0.1] * 1536
    mock_collection.aggregate.return_value = [
        {"_id": "id1", "score": 0.9, "payload": {"user_id": "alice", "agent_id": "agent1", "run_id": "run1"}},
    ]
    mock_collection.list_search_indexes.return_value = ["test_collection_vector_index"]

    filters = {"user_id": "alice", "agent_id": "agent1", "run_id": "run1"}
    results = mongo_vector.search("query_str", query_vector, limit=2, filters=filters)
    
    # Verify that the aggregation pipeline includes the filter stage
    mock_collection.aggregate.assert_called_once()
    pipeline = mock_collection.aggregate.call_args[0][0]
    
    # Check that the pipeline has the expected stages
    assert len(pipeline) == 4  # vectorSearch, match, set, project
    
    # Check that the match stage is present with the correct filters
    match_stage = pipeline[1]
    assert "$match" in match_stage
    assert match_stage["$match"]["$and"] == [
        {"payload.user_id": "alice"},
        {"payload.agent_id": "agent1"},
        {"payload.run_id": "run1"}
    ]
    
    assert len(results) == 1
    assert results[0].payload["user_id"] == "alice"
    assert results[0].payload["agent_id"] == "agent1"
    assert results[0].payload["run_id"] == "run1"


def test_search_with_single_filter(mongo_vector_fixture):
    """Test search with single filter."""
    mongo_vector, mock_collection, _ = mongo_vector_fixture
    query_vector = [0.1] * 1536
    mock_collection.aggregate.return_value = [
        {"_id": "id1", "score": 0.9, "payload": {"user_id": "alice"}},
    ]
    mock_collection.list_search_indexes.return_value = ["test_collection_vector_index"]

    filters = {"user_id": "alice"}
    results = mongo_vector.search("query_str", query_vector, limit=2, filters=filters)
    
    # Verify that the aggregation pipeline includes the filter stage
    mock_collection.aggregate.assert_called_once()
    pipeline = mock_collection.aggregate.call_args[0][0]
    
    # Check that the match stage is present with the correct filter
    match_stage = pipeline[1]
    assert "$match" in match_stage
    assert match_stage["$match"]["$and"] == [{"payload.user_id": "alice"}]
    
    assert len(results) == 1
    assert results[0].payload["user_id"] == "alice"


def test_search_with_no_filters(mongo_vector_fixture):
    """Test search with no filters."""
    mongo_vector, mock_collection, _ = mongo_vector_fixture
    query_vector = [0.1] * 1536
    mock_collection.aggregate.return_value = [
        {"_id": "id1", "score": 0.9, "payload": {"key": "value1"}},
    ]
    mock_collection.list_search_indexes.return_value = ["test_collection_vector_index"]

    results = mongo_vector.search("query_str", query_vector, limit=2, filters=None)
    
    # Verify that the aggregation pipeline does not include the filter stage
    mock_collection.aggregate.assert_called_once()
    pipeline = mock_collection.aggregate.call_args[0][0]
    
    # Check that the pipeline has only the expected stages (no match stage)
    assert len(pipeline) == 3  # vectorSearch, set, project
    
    assert len(results) == 1


def test_delete(mongo_vector_fixture):
    mongo_vector, mock_collection, _ = mongo_vector_fixture
    vector_id = "id1"
    mock_collection.delete_one.return_value = MagicMock(deleted_count=1)
    
    # Reset the mock to clear calls from fixture setup
    mock_collection.delete_one.reset_mock()

    mongo_vector.delete(vector_id=vector_id)

    mock_collection.delete_one.assert_called_once_with({"_id": vector_id})


def test_update(mongo_vector_fixture):
    mongo_vector, mock_collection, _ = mongo_vector_fixture
    vector_id = "id1"
    updated_vector = [0.3] * 1536
    updated_payload = {"name": "updated_vector"}

    mock_collection.update_one.return_value = MagicMock(matched_count=1)

    mongo_vector.update(vector_id=vector_id, vector=updated_vector, payload=updated_payload)

    mock_collection.update_one.assert_called_once_with(
        {"_id": vector_id}, {"$set": {"embedding": updated_vector, "payload": updated_payload}}
    )


def test_get(mongo_vector_fixture):
    mongo_vector, mock_collection, _ = mongo_vector_fixture
    vector_id = "id1"
    mock_collection.find_one.return_value = {"_id": vector_id, "payload": {"key": "value"}}

    result = mongo_vector.get(vector_id=vector_id)

    mock_collection.find_one.assert_called_once_with({"_id": vector_id})
    assert result.id == vector_id
    assert result.payload == {"key": "value"}


def test_list_cols(mongo_vector_fixture):
    mongo_vector, _, mock_db = mongo_vector_fixture
    mock_db.list_collection_names.return_value = ["collection1", "collection2"]
    
    # Reset the mock to clear calls from fixture setup
    mock_db.list_collection_names.reset_mock()

    result = mongo_vector.list_cols()

    mock_db.list_collection_names.assert_called_once()
    assert result == ["collection1", "collection2"]


def test_delete_col(mongo_vector_fixture):
    mongo_vector, mock_collection, _ = mongo_vector_fixture

    mongo_vector.delete_col()

    mock_collection.drop.assert_called_once()


def test_col_info(mongo_vector_fixture):
    mongo_vector, mock_collection, mock_db = mongo_vector_fixture
    mock_db.command.return_value = {"count": 10, "size": 1024}

    result = mongo_vector.col_info()

    mock_db.command.assert_called_once_with("collstats", "test_collection")
    assert result["name"] == "test_collection"
    assert result["count"] == 10
    assert result["size"] == 1024


def test_list(mongo_vector_fixture):
    mongo_vector, mock_collection, _ = mongo_vector_fixture
    # Mock the cursor to return the expected data
    mock_cursor = mock_collection.find.return_value
    mock_cursor.__iter__.return_value = [
        {"_id": "id1", "payload": {"key": "value1"}},
        {"_id": "id2", "payload": {"key": "value2"}},
    ]

    results = mongo_vector.list(limit=2)

    mock_collection.find.assert_called_once_with({})
    mock_cursor.limit.assert_called_once_with(2)
    assert len(results) == 2
    assert results[0].id == "id1"
    assert results[0].payload == {"key": "value1"}


def test_list_with_filters(mongo_vector_fixture):
    """Test list with agent_id and run_id filters."""
    mongo_vector, mock_collection, _ = mongo_vector_fixture
    # Mock the cursor to return the expected data
    mock_cursor = mock_collection.find.return_value
    mock_cursor.__iter__.return_value = [
        {"_id": "id1", "payload": {"user_id": "alice", "agent_id": "agent1", "run_id": "run1"}},
    ]

    filters = {"user_id": "alice", "agent_id": "agent1", "run_id": "run1"}
    results = mongo_vector.list(filters=filters, limit=2)
    
    # Verify that the find method was called with the correct query
    expected_query = {
        "$and": [
            {"payload.user_id": "alice"},
            {"payload.agent_id": "agent1"},
            {"payload.run_id": "run1"}
        ]
    }
    mock_collection.find.assert_called_once_with(expected_query)
    mock_cursor.limit.assert_called_once_with(2)
    
    assert len(results) == 1
    assert results[0].payload["user_id"] == "alice"
    assert results[0].payload["agent_id"] == "agent1"
    assert results[0].payload["run_id"] == "run1"


def test_list_with_single_filter(mongo_vector_fixture):
    """Test list with single filter."""
    mongo_vector, mock_collection, _ = mongo_vector_fixture
    # Mock the cursor to return the expected data
    mock_cursor = mock_collection.find.return_value
    mock_cursor.__iter__.return_value = [
        {"_id": "id1", "payload": {"user_id": "alice"}},
    ]

    filters = {"user_id": "alice"}
    results = mongo_vector.list(filters=filters, limit=2)
    
    # Verify that the find method was called with the correct query
    expected_query = {
        "$and": [
            {"payload.user_id": "alice"}
        ]
    }
    mock_collection.find.assert_called_once_with(expected_query)
    mock_cursor.limit.assert_called_once_with(2)
    
    assert len(results) == 1
    assert results[0].payload["user_id"] == "alice"


def test_list_with_no_filters(mongo_vector_fixture):
    """Test list with no filters."""
    mongo_vector, mock_collection, _ = mongo_vector_fixture
    # Mock the cursor to return the expected data
    mock_cursor = mock_collection.find.return_value
    mock_cursor.__iter__.return_value = [
        {"_id": "id1", "payload": {"key": "value1"}},
    ]

    results = mongo_vector.list(filters=None, limit=2)
    
    # Verify that the find method was called with empty query
    mock_collection.find.assert_called_once_with({})
    mock_cursor.limit.assert_called_once_with(2)
    
    assert len(results) == 1
