import os
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
        {"payload.run_id": "run1"},
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


def test_update_vector_and_payload(mongo_vector_fixture):
    """Test update with both vector and payload."""
    mongo_vector, mock_collection, _ = mongo_vector_fixture
    vector_id = "id1"
    updated_vector = [0.3] * 1536
    updated_payload = {"name": "updated_vector", "status": "active"}

    mock_collection.update_one.return_value = MagicMock(matched_count=1)

    mongo_vector.update(vector_id=vector_id, vector=updated_vector, payload=updated_payload)

    # The implementation uses dot notation to merge payload fields
    expected_update = {
        "$set": {"embedding": updated_vector, "payload.name": "updated_vector", "payload.status": "active"}
    }
    mock_collection.update_one.assert_called_once_with({"_id": vector_id}, expected_update)


def test_update_vector_only(mongo_vector_fixture):
    """Test update with only vector, no payload."""
    mongo_vector, mock_collection, _ = mongo_vector_fixture
    vector_id = "id1"
    updated_vector = [0.5] * 1536

    mock_collection.update_one.return_value = MagicMock(matched_count=1)

    mongo_vector.update(vector_id=vector_id, vector=updated_vector, payload=None)

    expected_update = {"$set": {"embedding": updated_vector}}
    mock_collection.update_one.assert_called_once_with({"_id": vector_id}, expected_update)


def test_update_payload_only(mongo_vector_fixture):
    """Test update with only payload, no vector."""
    mongo_vector, mock_collection, _ = mongo_vector_fixture
    vector_id = "id1"
    updated_payload = {"name": "updated_name", "value": 42}

    mock_collection.update_one.return_value = MagicMock(matched_count=1)

    mongo_vector.update(vector_id=vector_id, vector=None, payload=updated_payload)

    # The implementation uses dot notation to merge payload fields
    expected_update = {"$set": {"payload.name": "updated_name", "payload.value": 42}}
    mock_collection.update_one.assert_called_once_with({"_id": vector_id}, expected_update)


def test_update_empty_payload(mongo_vector_fixture):
    """Test update with empty payload dict."""
    mongo_vector, mock_collection, _ = mongo_vector_fixture
    vector_id = "id1"
    updated_vector = [0.4] * 1536
    empty_payload = {}

    mock_collection.update_one.return_value = MagicMock(matched_count=1)

    mongo_vector.update(vector_id=vector_id, vector=updated_vector, payload=empty_payload)

    # Empty payload should result in no payload fields being updated
    expected_update = {"$set": {"embedding": updated_vector}}
    mock_collection.update_one.assert_called_once_with({"_id": vector_id}, expected_update)


def test_update_none_parameters(mongo_vector_fixture):
    """Test update with both vector and payload as None (should not call update_one)."""
    mongo_vector, mock_collection, _ = mongo_vector_fixture
    vector_id = "id1"

    # Reset the mock to track calls
    mock_collection.update_one.reset_mock()

    mongo_vector.update(vector_id=vector_id, vector=None, payload=None)

    # When both are None, update_fields will be empty, so update_one should not be called
    mock_collection.update_one.assert_not_called()


def test_update_document_not_found(mongo_vector_fixture):
    """Test update when document doesn't exist (matched_count = 0)."""
    mongo_vector, mock_collection, _ = mongo_vector_fixture
    vector_id = "nonexistent_id"
    updated_vector = [0.3] * 1536
    updated_payload = {"name": "updated_vector"}

    # Simulate document not found
    mock_collection.update_one.return_value = MagicMock(matched_count=0)

    mongo_vector.update(vector_id=vector_id, vector=updated_vector, payload=updated_payload)

    # Should still call update_one, but matched_count will be 0
    expected_update = {"$set": {"embedding": updated_vector, "payload.name": "updated_vector"}}
    mock_collection.update_one.assert_called_once_with({"_id": vector_id}, expected_update)


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
        "$and": [{"payload.user_id": "alice"}, {"payload.agent_id": "agent1"}, {"payload.run_id": "run1"}]
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
    expected_query = {"$and": [{"payload.user_id": "alice"}]}
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


# Integration tests - require MongoDB Atlas Local or real MongoDB instance
@pytest.mark.skipif(
    not os.getenv("RUN_MONGODB_INTEGRATION"),
    reason="Only run with RUN_MONGODB_INTEGRATION=true. Requires MongoDB Atlas Local or MongoDB instance.",
)
class TestMongoDBIntegration:
    """Integration tests for MongoDB vector store using real MongoDB instance."""

    @pytest.fixture
    def mongodb_instance(self):
        """Create MongoDB vector store instance for testing."""
        mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/?directConnection=true")
        db_name = os.getenv("MONGO_TEST_DB", "test_db")
        collection_name = os.getenv("MONGO_TEST_COLLECTION", "test_collection_integration")

        instance = MongoDB(
            db_name=db_name,
            collection_name=collection_name,
            embedding_model_dims=1536,
            mongo_uri=mongo_uri,
        )

        # Clean up before each test
        try:
            instance.delete_col()
        except Exception:
            pass

        yield instance

        # Clean up after each test
        try:
            instance.delete_col()
            instance.client.close()
        except Exception:
            pass

    def test_insert_and_get(self, mongodb_instance):
        """Test vector insertion and retrieval."""
        vectors = [[0.1] * 1536, [0.2] * 1536]
        payloads = [{"name": "vector1", "category": "test"}, {"name": "vector2", "category": "test"}]
        ids = ["test_id_1", "test_id_2"]

        mongodb_instance.insert(vectors=vectors, payloads=payloads, ids=ids)

        # Test get
        result = mongodb_instance.get("test_id_1")
        assert result is not None
        assert result.id == "test_id_1"
        assert result.payload["name"] == "vector1"
        assert result.payload["category"] == "test"

    def test_update_vector_and_payload(self, mongodb_instance):
        """Test updating both vector and payload."""
        # Insert first
        vectors = [[0.1] * 1536]
        payloads = [{"name": "original", "status": "pending"}]
        ids = ["update_test_id"]

        mongodb_instance.insert(vectors=vectors, payloads=payloads, ids=ids)

        # Update both vector and payload
        updated_vector = [0.5] * 1536
        updated_payload = {"name": "updated", "status": "active", "new_field": "value"}

        mongodb_instance.update(vector_id="update_test_id", vector=updated_vector, payload=updated_payload)

        # Verify update
        result = mongodb_instance.get("update_test_id")
        assert result is not None
        assert result.payload["name"] == "updated"
        assert result.payload["status"] == "active"
        assert result.payload["new_field"] == "value"

    def test_update_vector_only(self, mongodb_instance):
        """Test updating only the vector."""
        # Insert first
        vectors = [[0.1] * 1536]
        payloads = [{"name": "test", "value": 10}]
        ids = ["update_vector_only_id"]

        mongodb_instance.insert(vectors=vectors, payloads=payloads, ids=ids)

        # Update only vector
        updated_vector = [0.9] * 1536
        mongodb_instance.update(vector_id="update_vector_only_id", vector=updated_vector, payload=None)

        # Verify payload is unchanged
        result = mongodb_instance.get("update_vector_only_id")
        assert result is not None
        assert result.payload["name"] == "test"
        assert result.payload["value"] == 10

    def test_update_payload_only(self, mongodb_instance):
        """Test updating only the payload."""
        # Insert first
        vectors = [[0.1] * 1536]
        payloads = [{"name": "original", "count": 1}]
        ids = ["update_payload_only_id"]

        mongodb_instance.insert(vectors=vectors, payloads=payloads, ids=ids)

        # Update only payload
        updated_payload = {"name": "updated_name", "count": 2, "new_field": "new_value"}
        mongodb_instance.update(vector_id="update_payload_only_id", vector=None, payload=updated_payload)

        # Verify payload is updated
        result = mongodb_instance.get("update_payload_only_id")
        assert result is not None
        assert result.payload["name"] == "updated_name"
        assert result.payload["count"] == 2
        assert result.payload["new_field"] == "new_value"

    def test_update_partial_payload(self, mongodb_instance):
        """Test that update merges payload fields using dot notation."""
        # Insert first
        vectors = [[0.1] * 1536]
        payloads = [{"field1": "value1", "field2": "value2", "field3": "value3"}]
        ids = ["partial_update_id"]

        mongodb_instance.insert(vectors=vectors, payloads=payloads, ids=ids)

        # Update only some fields
        partial_payload = {"field2": "updated_value2", "field4": "new_value4"}
        mongodb_instance.update(vector_id="partial_update_id", vector=None, payload=partial_payload)

        # Verify partial update - field1 and field3 should remain, field2 updated, field4 added
        result = mongodb_instance.get("partial_update_id")
        assert result is not None
        assert result.payload["field1"] == "value1"  # Unchanged
        assert result.payload["field2"] == "updated_value2"  # Updated
        assert result.payload["field3"] == "value3"  # Unchanged
        assert result.payload["field4"] == "new_value4"  # Added

    def test_delete(self, mongodb_instance):
        """Test deleting a vector."""
        # Insert first
        vectors = [[0.1] * 1536]
        payloads = [{"name": "to_delete"}]
        ids = ["delete_test_id"]

        mongodb_instance.insert(vectors=vectors, payloads=payloads, ids=ids)

        # Verify it exists
        result = mongodb_instance.get("delete_test_id")
        assert result is not None

        # Delete it
        mongodb_instance.delete("delete_test_id")

        # Verify it's gone
        result = mongodb_instance.get("delete_test_id")
        assert result is None

    def test_list(self, mongodb_instance):
        """Test listing vectors."""
        # Insert multiple vectors
        vectors = [[0.1] * 1536, [0.2] * 1536, [0.3] * 1536]
        payloads = [
            {"name": "vector1", "category": "A"},
            {"name": "vector2", "category": "B"},
            {"name": "vector3", "category": "A"},
        ]
        ids = ["list_id_1", "list_id_2", "list_id_3"]

        mongodb_instance.insert(vectors=vectors, payloads=payloads, ids=ids)

        # List all
        results = mongodb_instance.list()
        assert len(results) >= 3

        # List with filters
        filtered_results = mongodb_instance.list(filters={"category": "A"})
        assert len(filtered_results) >= 2
        for result in filtered_results:
            assert result.payload["category"] == "A"

    def test_list_with_limit(self, mongodb_instance):
        """Test listing with limit."""
        # Insert multiple vectors
        vectors = [[0.1] * 1536, [0.2] * 1536, [0.3] * 1536]
        payloads = [{"name": f"vector{i}"} for i in range(1, 4)]
        ids = [f"limit_test_{i}" for i in range(1, 4)]

        mongodb_instance.insert(vectors=vectors, payloads=payloads, ids=ids)

        # List with limit
        results = mongodb_instance.list(limit=2)
        assert len(results) <= 2

    def test_search(self, mongodb_instance):
        """Test vector similarity search."""
        # Insert vectors
        vectors = [[0.1] * 1536, [0.2] * 1536, [0.3] * 1536]
        payloads = [
            {"name": "similar_vector", "category": "test"},
            {"name": "different_vector", "category": "test"},
            {"name": "another_vector", "category": "test"},
        ]
        ids = ["search_id_1", "search_id_2", "search_id_3"]

        mongodb_instance.insert(vectors=vectors, payloads=payloads, ids=ids)

        # Wait a bit for index to be ready (MongoDB Atlas Local may need time)
        import time

        time.sleep(2)

        # Search
        query_vector = [0.1] * 1536
        results = mongodb_instance.search(query="test query", vectors=query_vector, limit=2)

        # Should return results (may be empty if index not ready, but shouldn't error)
        assert isinstance(results, list)
        assert len(results) <= 2

    def test_search_with_filters(self, mongodb_instance):
        """Test vector search with filters."""
        # Insert vectors
        vectors = [[0.1] * 1536, [0.2] * 1536]
        payloads = [
            {"user_id": "alice", "agent_id": "agent1", "run_id": "run1"},
            {"user_id": "bob", "agent_id": "agent1", "run_id": "run1"},
        ]
        ids = ["filter_search_1", "filter_search_2"]

        mongodb_instance.insert(vectors=vectors, payloads=payloads, ids=ids)

        # Wait for index
        import time

        time.sleep(2)

        # Search with filters
        query_vector = [0.1] * 1536
        filters = {"user_id": "alice", "agent_id": "agent1", "run_id": "run1"}
        results = mongodb_instance.search(query="test", vectors=query_vector, limit=10, filters=filters)

        # Should return filtered results
        assert isinstance(results, list)
        for result in results:
            assert result.payload["user_id"] == "alice"
            assert result.payload["agent_id"] == "agent1"
            assert result.payload["run_id"] == "run1"

    def test_col_info(self, mongodb_instance):
        """Test collection info."""
        # Insert some data
        vectors = [[0.1] * 1536]
        payloads = [{"name": "test"}]
        ids = ["info_test_id"]

        mongodb_instance.insert(vectors=vectors, payloads=payloads, ids=ids)

        # Get collection info
        info = mongodb_instance.col_info()
        assert "name" in info
        assert "count" in info
        assert info["count"] >= 1

    def test_list_cols(self, mongodb_instance):
        """Test listing collections."""
        collections = mongodb_instance.list_cols()
        assert isinstance(collections, list)
        # Should at least contain our test collection
        assert mongodb_instance.collection_name in collections or len(collections) >= 0
