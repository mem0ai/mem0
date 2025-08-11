import unittest
import uuid
from unittest.mock import MagicMock

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    Filter,
    PointIdsList,
    PointStruct,
    VectorParams,
)

from mem0.vector_stores.qdrant import Qdrant


class TestQdrant(unittest.TestCase):
    def setUp(self):
        self.client_mock = MagicMock(spec=QdrantClient)
        self.qdrant = Qdrant(
            collection_name="test_collection",
            embedding_model_dims=128,
            client=self.client_mock,
            path="test_path",
            on_disk=True,
        )

    def test_create_col(self):
        self.client_mock.get_collections.return_value = MagicMock(collections=[])

        self.qdrant.create_col(vector_size=128, on_disk=True)

        expected_config = VectorParams(size=128, distance=Distance.COSINE, on_disk=True)

        self.client_mock.create_collection.assert_called_with(
            collection_name="test_collection", vectors_config=expected_config
        )

    def test_insert(self):
        vectors = [[0.1, 0.2], [0.3, 0.4]]
        payloads = [{"key": "value1"}, {"key": "value2"}]
        ids = [str(uuid.uuid4()), str(uuid.uuid4())]

        self.qdrant.insert(vectors=vectors, payloads=payloads, ids=ids)

        self.client_mock.upsert.assert_called_once()
        points = self.client_mock.upsert.call_args[1]["points"]

        self.assertEqual(len(points), 2)
        for point in points:
            self.assertIsInstance(point, PointStruct)

        self.assertEqual(points[0].payload, payloads[0])

    def test_search(self):
        vectors = [[0.1, 0.2]]
        mock_point = MagicMock(id=str(uuid.uuid4()), score=0.95, payload={"key": "value"})
        self.client_mock.query_points.return_value = MagicMock(points=[mock_point])

        results = self.qdrant.search(query="", vectors=vectors, limit=1)

        self.client_mock.query_points.assert_called_once_with(
            collection_name="test_collection",
            query=vectors,
            query_filter=None,
            limit=1,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].payload, {"key": "value"})
        self.assertEqual(results[0].score, 0.95)

    def test_search_with_filters(self):
        """Test search with agent_id and run_id filters."""
        vectors = [[0.1, 0.2]]
        mock_point = MagicMock(
            id=str(uuid.uuid4()), 
            score=0.95, 
            payload={"user_id": "alice", "agent_id": "agent1", "run_id": "run1"}
        )
        self.client_mock.query_points.return_value = MagicMock(points=[mock_point])

        filters = {"user_id": "alice", "agent_id": "agent1", "run_id": "run1"}
        results = self.qdrant.search(query="", vectors=vectors, limit=1, filters=filters)

        # Verify that _create_filter was called and query_filter was passed
        self.client_mock.query_points.assert_called_once()
        call_args = self.client_mock.query_points.call_args[1]
        self.assertEqual(call_args["collection_name"], "test_collection")
        self.assertEqual(call_args["query"], vectors)
        self.assertEqual(call_args["limit"], 1)
        
        # Verify that a Filter object was created
        query_filter = call_args["query_filter"]
        self.assertIsInstance(query_filter, Filter)
        self.assertEqual(len(query_filter.must), 3)  # user_id, agent_id, run_id

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].payload["user_id"], "alice")
        self.assertEqual(results[0].payload["agent_id"], "agent1")
        self.assertEqual(results[0].payload["run_id"], "run1")

    def test_search_with_single_filter(self):
        """Test search with single filter."""
        vectors = [[0.1, 0.2]]
        mock_point = MagicMock(
            id=str(uuid.uuid4()), 
            score=0.95, 
            payload={"user_id": "alice"}
        )
        self.client_mock.query_points.return_value = MagicMock(points=[mock_point])

        filters = {"user_id": "alice"}
        results = self.qdrant.search(query="", vectors=vectors, limit=1, filters=filters)

        # Verify that a Filter object was created with single condition
        call_args = self.client_mock.query_points.call_args[1]
        query_filter = call_args["query_filter"]
        self.assertIsInstance(query_filter, Filter)
        self.assertEqual(len(query_filter.must), 1)  # Only user_id

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].payload["user_id"], "alice")

    def test_search_with_no_filters(self):
        """Test search with no filters."""
        vectors = [[0.1, 0.2]]
        mock_point = MagicMock(id=str(uuid.uuid4()), score=0.95, payload={"key": "value"})
        self.client_mock.query_points.return_value = MagicMock(points=[mock_point])

        results = self.qdrant.search(query="", vectors=vectors, limit=1, filters=None)

        call_args = self.client_mock.query_points.call_args[1]
        self.assertIsNone(call_args["query_filter"])

        self.assertEqual(len(results), 1)

    def test_create_filter_multiple_filters(self):
        """Test _create_filter with multiple filters."""
        filters = {"user_id": "alice", "agent_id": "agent1", "run_id": "run1"}
        result = self.qdrant._create_filter(filters)
        
        self.assertIsInstance(result, Filter)
        self.assertEqual(len(result.must), 3)
        
        # Check that all conditions are present
        conditions = [cond.key for cond in result.must]
        self.assertIn("user_id", conditions)
        self.assertIn("agent_id", conditions)
        self.assertIn("run_id", conditions)

    def test_create_filter_single_filter(self):
        """Test _create_filter with single filter."""
        filters = {"user_id": "alice"}
        result = self.qdrant._create_filter(filters)
        
        self.assertIsInstance(result, Filter)
        self.assertEqual(len(result.must), 1)
        self.assertEqual(result.must[0].key, "user_id")
        self.assertEqual(result.must[0].match.value, "alice")

    def test_create_filter_no_filters(self):
        """Test _create_filter with no filters."""
        result = self.qdrant._create_filter(None)
        self.assertIsNone(result)
        
        result = self.qdrant._create_filter({})
        self.assertIsNone(result)

    def test_create_filter_with_range_values(self):
        """Test _create_filter with range values."""
        filters = {"user_id": "alice", "count": {"gte": 5, "lte": 10}}
        result = self.qdrant._create_filter(filters)
        
        self.assertIsInstance(result, Filter)
        self.assertEqual(len(result.must), 2)
        
        # Check that range condition is created
        range_conditions = [cond for cond in result.must if hasattr(cond, 'range') and cond.range is not None]
        self.assertEqual(len(range_conditions), 1)
        self.assertEqual(range_conditions[0].key, "count")
        
        # Check that string condition is created
        string_conditions = [cond for cond in result.must if hasattr(cond, 'match') and cond.match is not None]
        self.assertEqual(len(string_conditions), 1)
        self.assertEqual(string_conditions[0].key, "user_id")

    def test_delete(self):
        vector_id = str(uuid.uuid4())
        self.qdrant.delete(vector_id=vector_id)

        self.client_mock.delete.assert_called_once_with(
            collection_name="test_collection",
            points_selector=PointIdsList(points=[vector_id]),
        )

    def test_update(self):
        vector_id = str(uuid.uuid4())
        updated_vector = [0.2, 0.3]
        updated_payload = {"key": "updated_value"}

        self.qdrant.update(vector_id=vector_id, vector=updated_vector, payload=updated_payload)

        self.client_mock.upsert.assert_called_once()
        point = self.client_mock.upsert.call_args[1]["points"][0]
        self.assertEqual(point.id, vector_id)
        self.assertEqual(point.vector, updated_vector)
        self.assertEqual(point.payload, updated_payload)

    def test_get(self):
        vector_id = str(uuid.uuid4())
        self.client_mock.retrieve.return_value = [{"id": vector_id, "payload": {"key": "value"}}]

        result = self.qdrant.get(vector_id=vector_id)

        self.client_mock.retrieve.assert_called_once_with(
            collection_name="test_collection", ids=[vector_id], with_payload=True
        )
        self.assertEqual(result["id"], vector_id)
        self.assertEqual(result["payload"], {"key": "value"})

    def test_list_cols(self):
        self.client_mock.get_collections.return_value = MagicMock(collections=[{"name": "test_collection"}])
        result = self.qdrant.list_cols()
        self.assertEqual(result.collections[0]["name"], "test_collection")

    def test_list_with_filters(self):
        """Test list with agent_id and run_id filters."""
        mock_point = MagicMock(
            id=str(uuid.uuid4()), 
            score=0.95, 
            payload={"user_id": "alice", "agent_id": "agent1", "run_id": "run1"}
        )
        self.client_mock.scroll.return_value = [mock_point]

        filters = {"user_id": "alice", "agent_id": "agent1", "run_id": "run1"}
        results = self.qdrant.list(filters=filters, limit=10)

        # Verify that _create_filter was called and scroll_filter was passed
        self.client_mock.scroll.assert_called_once()
        call_args = self.client_mock.scroll.call_args[1]
        self.assertEqual(call_args["collection_name"], "test_collection")
        self.assertEqual(call_args["limit"], 10)
        
        # Verify that a Filter object was created
        scroll_filter = call_args["scroll_filter"]
        self.assertIsInstance(scroll_filter, Filter)
        self.assertEqual(len(scroll_filter.must), 3)  # user_id, agent_id, run_id

        # The list method returns the result directly
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].payload["user_id"], "alice")
        self.assertEqual(results[0].payload["agent_id"], "agent1")
        self.assertEqual(results[0].payload["run_id"], "run1")

    def test_list_with_single_filter(self):
        """Test list with single filter."""
        mock_point = MagicMock(
            id=str(uuid.uuid4()), 
            score=0.95, 
            payload={"user_id": "alice"}
        )
        self.client_mock.scroll.return_value = [mock_point]

        filters = {"user_id": "alice"}
        results = self.qdrant.list(filters=filters, limit=10)

        # Verify that a Filter object was created with single condition
        call_args = self.client_mock.scroll.call_args[1]
        scroll_filter = call_args["scroll_filter"]
        self.assertIsInstance(scroll_filter, Filter)
        self.assertEqual(len(scroll_filter.must), 1)  # Only user_id

        # The list method returns the result directly
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].payload["user_id"], "alice")

    def test_list_with_no_filters(self):
        """Test list with no filters."""
        mock_point = MagicMock(id=str(uuid.uuid4()), score=0.95, payload={"key": "value"})
        self.client_mock.scroll.return_value = [mock_point]

        results = self.qdrant.list(filters=None, limit=10)

        call_args = self.client_mock.scroll.call_args[1]
        self.assertIsNone(call_args["scroll_filter"])

        # The list method returns the result directly
        self.assertEqual(len(results), 1)

    def test_delete_col(self):
        self.qdrant.delete_col()
        self.client_mock.delete_collection.assert_called_once_with(collection_name="test_collection")

    def test_col_info(self):
        self.qdrant.col_info()
        self.client_mock.get_collection.assert_called_once_with(collection_name="test_collection")

    def tearDown(self):
        del self.qdrant
