import unittest
import uuid
from unittest.mock import MagicMock

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    MatchExcept,
    MatchText,
    MatchValue,
    PointIdsList,
    PointStruct,
    Range,
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


class TestQdrantEnhancedFilters(unittest.TestCase):
    """Tests for enhanced metadata filtering operators (issue #3975)."""

    def setUp(self):
        self.client_mock = MagicMock(spec=QdrantClient)
        self.qdrant = Qdrant(
            collection_name="test_collection",
            embedding_model_dims=128,
            client=self.client_mock,
        )

    # ------------------------------------------------------------------ #
    # _build_field_condition                                               #
    # ------------------------------------------------------------------ #

    def test_simple_equality(self):
        """Plain value maps to MatchValue."""
        cond = self.qdrant._build_field_condition("category", "programming")
        self.assertIsInstance(cond, FieldCondition)
        self.assertEqual(cond.key, "category")
        self.assertIsInstance(cond.match, MatchValue)
        self.assertEqual(cond.match.value, "programming")

    def test_eq_operator(self):
        """{\"eq\": v} maps to MatchValue."""
        cond = self.qdrant._build_field_condition("category", {"eq": "programming"})
        self.assertIsInstance(cond.match, MatchValue)
        self.assertEqual(cond.match.value, "programming")

    def test_ne_operator(self):
        """{\"ne\": v} maps to MatchExcept with a single-element list."""
        cond = self.qdrant._build_field_condition("category", {"ne": "spam"})
        self.assertIsInstance(cond.match, MatchExcept)
        self.assertIn("spam", getattr(cond.match, "except_", None) or getattr(cond.match, "except"))

    def test_in_operator(self):
        """{\"in\": [...]} maps to MatchAny."""
        cond = self.qdrant._build_field_condition("category", {"in": ["a", "b", "c"]})
        self.assertIsInstance(cond.match, MatchAny)
        self.assertEqual(cond.match.any, ["a", "b", "c"])

    def test_nin_operator(self):
        """{\"nin\": [...]} maps to MatchExcept."""
        cond = self.qdrant._build_field_condition("status", {"nin": ["deleted", "banned"]})
        self.assertIsInstance(cond.match, MatchExcept)
        excluded = getattr(cond.match, "except_", None) or getattr(cond.match, "except")
        self.assertIn("deleted", excluded)
        self.assertIn("banned", excluded)

    def test_contains_operator(self):
        """{\"contains\": x} maps to MatchText."""
        cond = self.qdrant._build_field_condition("bio", {"contains": "python"})
        self.assertIsInstance(cond.match, MatchText)
        self.assertEqual(cond.match.text, "python")

    def test_icontains_operator(self):
        """{\"icontains\": x} maps to MatchText (same as contains for Qdrant)."""
        cond = self.qdrant._build_field_condition("bio", {"icontains": "Python"})
        self.assertIsInstance(cond.match, MatchText)
        self.assertEqual(cond.match.text, "Python")

    def test_gt_operator(self):
        """{\"gt\": v} maps to Range with gt only."""
        cond = self.qdrant._build_field_condition("priority", {"gt": 5})
        self.assertIsInstance(cond.range, Range)
        self.assertEqual(cond.range.gt, 5)
        self.assertIsNone(cond.range.gte)
        self.assertIsNone(cond.range.lt)
        self.assertIsNone(cond.range.lte)

    def test_gte_operator(self):
        """{\"gte\": v} maps to Range with gte only."""
        cond = self.qdrant._build_field_condition("priority", {"gte": 5})
        self.assertIsInstance(cond.range, Range)
        self.assertEqual(cond.range.gte, 5)
        self.assertIsNone(cond.range.gt)

    def test_lt_operator(self):
        """{\"lt\": v} maps to Range with lt only."""
        cond = self.qdrant._build_field_condition("priority", {"lt": 10})
        self.assertIsInstance(cond.range, Range)
        self.assertEqual(cond.range.lt, 10)

    def test_lte_operator(self):
        """{\"lte\": v} maps to Range with lte only."""
        cond = self.qdrant._build_field_condition("priority", {"lte": 10})
        self.assertIsInstance(cond.range, Range)
        self.assertEqual(cond.range.lte, 10)

    def test_range_gte_lte(self):
        """Combined {\"gte\": x, \"lte\": y} maps to Range with both bounds."""
        cond = self.qdrant._build_field_condition("priority", {"gte": 5, "lte": 10})
        self.assertIsInstance(cond.range, Range)
        self.assertEqual(cond.range.gte, 5)
        self.assertEqual(cond.range.lte, 10)

    def test_range_gt_lt(self):
        """Open interval {\"gt\": x, \"lt\": y} maps to Range with both bounds."""
        cond = self.qdrant._build_field_condition("score", {"gt": 0.5, "lt": 0.9})
        self.assertIsInstance(cond.range, Range)
        self.assertEqual(cond.range.gt, 0.5)
        self.assertEqual(cond.range.lt, 0.9)

    # ------------------------------------------------------------------ #
    # _create_filter — comparison and list operators                       #
    # ------------------------------------------------------------------ #

    def test_create_filter_eq(self):
        result = self.qdrant._create_filter({"category": {"eq": "programming"}})
        self.assertIsInstance(result, Filter)
        self.assertEqual(len(result.must), 1)
        self.assertIsInstance(result.must[0].match, MatchValue)

    def test_create_filter_ne(self):
        result = self.qdrant._create_filter({"category": {"ne": "spam"}})
        self.assertIsInstance(result, Filter)
        self.assertIsInstance(result.must[0].match, MatchExcept)

    def test_create_filter_in(self):
        result = self.qdrant._create_filter({"category": {"in": ["prog", "data"]}})
        self.assertIsInstance(result, Filter)
        self.assertIsInstance(result.must[0].match, MatchAny)
        self.assertEqual(result.must[0].match.any, ["prog", "data"])

    def test_create_filter_nin(self):
        result = self.qdrant._create_filter({"status": {"nin": ["deleted", "banned"]}})
        self.assertIsInstance(result, Filter)
        self.assertIsInstance(result.must[0].match, MatchExcept)

    def test_create_filter_gt(self):
        result = self.qdrant._create_filter({"priority": {"gt": 7}})
        self.assertIsInstance(result, Filter)
        self.assertIsInstance(result.must[0].range, Range)
        self.assertEqual(result.must[0].range.gt, 7)

    def test_create_filter_gte_lte_range(self):
        result = self.qdrant._create_filter({"priority": {"gte": 5, "lte": 9}})
        self.assertIsInstance(result, Filter)
        r = result.must[0].range
        self.assertEqual(r.gte, 5)
        self.assertEqual(r.lte, 9)

    def test_create_filter_contains(self):
        result = self.qdrant._create_filter({"bio": {"contains": "python"}})
        self.assertIsInstance(result, Filter)
        self.assertIsInstance(result.must[0].match, MatchText)

    # ------------------------------------------------------------------ #
    # _create_filter — logical operators                                   #
    # ------------------------------------------------------------------ #

    def test_and_operator(self):
        """AND populates Filter.must with nested Filter objects."""
        filters = {"AND": [{"category": "programming"}, {"priority": 10}]}
        result = self.qdrant._create_filter(filters)
        self.assertIsInstance(result, Filter)
        self.assertEqual(len(result.must), 2)
        # Each item is a Filter that wraps a single FieldCondition
        for item in result.must:
            self.assertIsInstance(item, Filter)

    def test_or_operator(self):
        """OR populates Filter.should with nested Filter objects."""
        filters = {"OR": [{"category": "programming"}, {"category": "data"}]}
        result = self.qdrant._create_filter(filters)
        self.assertIsInstance(result, Filter)
        self.assertEqual(len(result.should), 2)
        self.assertIsNone(result.must)

    def test_not_operator(self):
        """NOT populates Filter.must_not with nested Filter objects."""
        filters = {"NOT": [{"category": "spam"}]}
        result = self.qdrant._create_filter(filters)
        self.assertIsInstance(result, Filter)
        self.assertEqual(len(result.must_not), 1)
        self.assertIsNone(result.must)
        self.assertIsNone(result.should)

    def test_mixed_field_and_and(self):
        """Top-level field conditions and AND can coexist in must."""
        filters = {
            "user_id": "alice",
            "AND": [{"priority": {"gte": 5}}, {"category": "programming"}],
        }
        result = self.qdrant._create_filter(filters)
        self.assertIsInstance(result, Filter)
        # user_id FieldCondition + 2 nested AND Filters = 3 items in must
        self.assertEqual(len(result.must), 3)

    def test_nested_and_or(self):
        """AND containing an OR sub-condition produces correct nesting."""
        filters = {
            "AND": [
                {"OR": [{"category": "prog"}, {"category": "data"}]},
                {"priority": {"gt": 3}},
            ]
        }
        result = self.qdrant._create_filter(filters)
        self.assertIsInstance(result, Filter)
        self.assertEqual(len(result.must), 2)
        # First item is a Filter with should (the OR)
        or_filter = result.must[0]
        self.assertIsInstance(or_filter, Filter)
        self.assertEqual(len(or_filter.should), 2)

    # ------------------------------------------------------------------ #
    # Edge cases                                                           #
    # ------------------------------------------------------------------ #

    def test_empty_filter_returns_none(self):
        self.assertIsNone(self.qdrant._create_filter({}))
        self.assertIsNone(self.qdrant._create_filter(None))

    def test_backward_compat_simple_equality(self):
        """Plain scalar equality still works as before."""
        result = self.qdrant._create_filter({"user_id": "alice", "run_id": "r1"})
        self.assertIsInstance(result, Filter)
        keys = [c.key for c in result.must]
        self.assertIn("user_id", keys)
        self.assertIn("run_id", keys)

    def test_backward_compat_gte_lte_range(self):
        """Original gte+lte range filter still produces a Range condition."""
        result = self.qdrant._create_filter({"count": {"gte": 5, "lte": 10}})
        self.assertIsInstance(result, Filter)
        self.assertIsInstance(result.must[0].range, Range)
        self.assertEqual(result.must[0].range.gte, 5)
        self.assertEqual(result.must[0].range.lte, 10)

    def tearDown(self):
        del self.qdrant
