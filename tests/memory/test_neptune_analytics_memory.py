import unittest
from unittest.mock import MagicMock, patch
import pytest
from mem0.graphs.neptune.neptunegraph import MemoryGraph
from mem0.graphs.neptune.base import NeptuneBase


class TestNeptuneMemory(unittest.TestCase):
    """Test suite for the Neptune Memory implementation."""

    def setUp(self):
        """Set up test fixtures before each test method."""

        # Create a mock config
        self.config = MagicMock()
        self.config.graph_store.config.endpoint = "neptune-graph://test-graph"
        self.config.graph_store.config.base_label = True
        self.config.llm.provider = "openai_structured"
        self.config.graph_store.llm = None
        self.config.graph_store.custom_prompt = None

        # Create mock for NeptuneAnalyticsGraph
        self.mock_graph = MagicMock()
        self.mock_graph.client.get_graph.return_value = {"status": "AVAILABLE"}

        # Create mocks for static methods
        self.mock_embedding_model = MagicMock()
        self.mock_llm = MagicMock()

        # Patch the necessary components
        self.neptune_analytics_graph_patcher = patch("mem0.graphs.neptune.neptunegraph.NeptuneAnalyticsGraph")
        self.mock_neptune_analytics_graph = self.neptune_analytics_graph_patcher.start()
        self.mock_neptune_analytics_graph.return_value = self.mock_graph

        # Patch the static methods
        self.create_embedding_model_patcher = patch.object(NeptuneBase, "_create_embedding_model")
        self.mock_create_embedding_model = self.create_embedding_model_patcher.start()
        self.mock_create_embedding_model.return_value = self.mock_embedding_model

        self.create_llm_patcher = patch.object(NeptuneBase, "_create_llm")
        self.mock_create_llm = self.create_llm_patcher.start()
        self.mock_create_llm.return_value = self.mock_llm

        # Create the MemoryGraph instance
        self.memory_graph = MemoryGraph(self.config)

        # Set up common test data
        self.user_id = "test_user"
        self.test_filters = {"user_id": self.user_id}

    def tearDown(self):
        """Tear down test fixtures after each test method."""
        self.neptune_analytics_graph_patcher.stop()
        self.create_embedding_model_patcher.stop()
        self.create_llm_patcher.stop()

    def test_initialization(self):
        """Test that the MemoryGraph is initialized correctly."""
        self.assertEqual(self.memory_graph.graph, self.mock_graph)
        self.assertEqual(self.memory_graph.embedding_model, self.mock_embedding_model)
        self.assertEqual(self.memory_graph.llm, self.mock_llm)
        self.assertEqual(self.memory_graph.llm_provider, "openai_structured")
        self.assertEqual(self.memory_graph.node_label, ":`__Entity__`")
        self.assertEqual(self.memory_graph.threshold, 0.7)

    def test_init(self):
        """Test the class init functions"""

        # Create a mock config with bad endpoint
        config_no_endpoint = MagicMock()
        config_no_endpoint.graph_store.config.endpoint = None

        # Create the MemoryGraph instance
        with pytest.raises(ValueError):
            MemoryGraph(config_no_endpoint)

        # Create a mock config with bad endpoint
        config_ndb_endpoint = MagicMock()
        config_ndb_endpoint.graph_store.config.endpoint = "neptune-db://test-graph"

        with pytest.raises(ValueError):
            MemoryGraph(config_ndb_endpoint)

    def test_add_method(self):
        """Test the add method with mocked components."""

        # Mock the necessary methods that add() calls
        self.memory_graph._retrieve_nodes_from_data = MagicMock(return_value={"alice": "person", "bob": "person"})
        self.memory_graph._establish_nodes_relations_from_data = MagicMock(
            return_value=[{"source": "alice", "relationship": "knows", "destination": "bob"}]
        )
        self.memory_graph._search_graph_db = MagicMock(return_value=[])
        self.memory_graph._get_delete_entities_from_search_output = MagicMock(return_value=[])
        self.memory_graph._delete_entities = MagicMock(return_value=[])
        self.memory_graph._add_entities = MagicMock(
            return_value=[{"source": "alice", "relationship": "knows", "target": "bob"}]
        )

        # Call the add method
        result = self.memory_graph.add("Alice knows Bob", self.test_filters)

        # Verify the method calls
        self.memory_graph._retrieve_nodes_from_data.assert_called_once_with("Alice knows Bob", self.test_filters)
        self.memory_graph._establish_nodes_relations_from_data.assert_called_once()
        self.memory_graph._search_graph_db.assert_called_once()
        self.memory_graph._get_delete_entities_from_search_output.assert_called_once()
        self.memory_graph._delete_entities.assert_called_once_with([], self.user_id)
        self.memory_graph._add_entities.assert_called_once()

        # Check the result structure
        self.assertIn("deleted_entities", result)
        self.assertIn("added_entities", result)

    def test_search_method(self):
        """Test the search method with mocked components."""
        # Mock the necessary methods that search() calls
        self.memory_graph._retrieve_nodes_from_data = MagicMock(return_value={"alice": "person"})

        # Mock search results
        mock_search_results = [
            {"source": "alice", "relationship": "knows", "destination": "bob"},
            {"source": "alice", "relationship": "works_with", "destination": "charlie"},
        ]
        self.memory_graph._search_graph_db = MagicMock(return_value=mock_search_results)

        # Mock BM25Okapi
        with patch("mem0.graphs.neptune.base.BM25Okapi") as mock_bm25:
            mock_bm25_instance = MagicMock()
            mock_bm25.return_value = mock_bm25_instance

            # Mock get_top_n to return reranked results
            reranked_results = [["alice", "knows", "bob"], ["alice", "works_with", "charlie"]]
            mock_bm25_instance.get_top_n.return_value = reranked_results

            # Call the search method
            result = self.memory_graph.search("Find Alice", self.test_filters, limit=5)

            # Verify the method calls
            self.memory_graph._retrieve_nodes_from_data.assert_called_once_with("Find Alice", self.test_filters)
            self.memory_graph._search_graph_db.assert_called_once_with(node_list=["alice"], filters=self.test_filters)

            # Check the result structure
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]["source"], "alice")
            self.assertEqual(result[0]["relationship"], "knows")
            self.assertEqual(result[0]["destination"], "bob")

    def test_get_all_method(self):
        """Test the get_all method."""

        # Mock the _get_all_cypher method
        mock_cypher = "MATCH (n) RETURN n"
        mock_params = {"user_id": self.user_id, "limit": 10}
        self.memory_graph._get_all_cypher = MagicMock(return_value=(mock_cypher, mock_params))

        # Mock the graph.query result
        mock_query_result = [
            {"source": "alice", "relationship": "knows", "target": "bob"},
            {"source": "bob", "relationship": "works_with", "target": "charlie"},
        ]
        self.mock_graph.query.return_value = mock_query_result

        # Call the get_all method
        result = self.memory_graph.get_all(self.test_filters, limit=10)

        # Verify the method calls
        self.memory_graph._get_all_cypher.assert_called_once_with(self.test_filters, 10)
        self.mock_graph.query.assert_called_once_with(mock_cypher, params=mock_params)

        # Check the result structure
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["source"], "alice")
        self.assertEqual(result[0]["relationship"], "knows")
        self.assertEqual(result[0]["target"], "bob")

    def test_delete_all_method(self):
        """Test the delete_all method."""
        # Mock the _delete_all_cypher method
        mock_cypher = "MATCH (n) DETACH DELETE n"
        mock_params = {"user_id": self.user_id}
        self.memory_graph._delete_all_cypher = MagicMock(return_value=(mock_cypher, mock_params))

        # Call the delete_all method
        self.memory_graph.delete_all(self.test_filters)

        # Verify the method calls
        self.memory_graph._delete_all_cypher.assert_called_once_with(self.test_filters)
        self.mock_graph.query.assert_called_once_with(mock_cypher, params=mock_params)

    def test_search_source_node(self):
        """Test the _search_source_node method."""
        # Mock embedding
        mock_embedding = [0.1, 0.2, 0.3]

        # Mock the _search_source_node_cypher method
        mock_cypher = "MATCH (n) RETURN n"
        mock_params = {"source_embedding": mock_embedding, "user_id": self.user_id, "threshold": 0.9}
        self.memory_graph._search_source_node_cypher = MagicMock(return_value=(mock_cypher, mock_params))

        # Mock the graph.query result
        mock_query_result = [{"id(source_candidate)": 123, "cosine_similarity": 0.95}]
        self.mock_graph.query.return_value = mock_query_result

        # Call the _search_source_node method
        result = self.memory_graph._search_source_node(mock_embedding, self.user_id, threshold=0.9)

        # Verify the method calls
        self.memory_graph._search_source_node_cypher.assert_called_once_with(mock_embedding, self.user_id, 0.9)
        self.mock_graph.query.assert_called_once_with(mock_cypher, params=mock_params)

        # Check the result
        self.assertEqual(result, mock_query_result)

    def test_search_destination_node(self):
        """Test the _search_destination_node method."""
        # Mock embedding
        mock_embedding = [0.1, 0.2, 0.3]

        # Mock the _search_destination_node_cypher method
        mock_cypher = "MATCH (n) RETURN n"
        mock_params = {"destination_embedding": mock_embedding, "user_id": self.user_id, "threshold": 0.9}
        self.memory_graph._search_destination_node_cypher = MagicMock(return_value=(mock_cypher, mock_params))

        # Mock the graph.query result
        mock_query_result = [{"id(destination_candidate)": 456, "cosine_similarity": 0.92}]
        self.mock_graph.query.return_value = mock_query_result

        # Call the _search_destination_node method
        result = self.memory_graph._search_destination_node(mock_embedding, self.user_id, threshold=0.9)

        # Verify the method calls
        self.memory_graph._search_destination_node_cypher.assert_called_once_with(mock_embedding, self.user_id, 0.9)
        self.mock_graph.query.assert_called_once_with(mock_cypher, params=mock_params)

        # Check the result
        self.assertEqual(result, mock_query_result)

    def test_search_graph_db(self):
        """Test the _search_graph_db method."""
        # Mock node list
        node_list = ["alice", "bob"]

        # Mock embedding
        mock_embedding = [0.1, 0.2, 0.3]
        self.mock_embedding_model.embed.return_value = mock_embedding

        # Mock the _search_graph_db_cypher method
        mock_cypher = "MATCH (n) RETURN n"
        mock_params = {"n_embedding": mock_embedding, "user_id": self.user_id, "threshold": 0.7, "limit": 10}
        self.memory_graph._search_graph_db_cypher = MagicMock(return_value=(mock_cypher, mock_params))

        # Mock the graph.query results
        mock_query_result1 = [{"source": "alice", "relationship": "knows", "destination": "bob"}]
        mock_query_result2 = [{"source": "bob", "relationship": "works_with", "destination": "charlie"}]
        self.mock_graph.query.side_effect = [mock_query_result1, mock_query_result2]

        # Call the _search_graph_db method
        result = self.memory_graph._search_graph_db(node_list, self.test_filters, limit=10)

        # Verify the method calls
        self.assertEqual(self.mock_embedding_model.embed.call_count, 2)
        self.assertEqual(self.memory_graph._search_graph_db_cypher.call_count, 2)
        self.assertEqual(self.mock_graph.query.call_count, 2)

        # Check the result
        expected_result = mock_query_result1 + mock_query_result2
        self.assertEqual(result, expected_result)

    def test_add_entities(self):
        """Test the _add_entities method."""
        # Mock data
        to_be_added = [{"source": "alice", "relationship": "knows", "destination": "bob"}]
        entity_type_map = {"alice": "person", "bob": "person"}

        # Mock embeddings
        mock_embedding = [0.1, 0.2, 0.3]
        self.mock_embedding_model.embed.return_value = mock_embedding

        # Mock search results
        mock_source_search = [{"id(source_candidate)": 123, "cosine_similarity": 0.95}]
        mock_dest_search = [{"id(destination_candidate)": 456, "cosine_similarity": 0.92}]

        # Mock the search methods
        self.memory_graph._search_source_node = MagicMock(return_value=mock_source_search)
        self.memory_graph._search_destination_node = MagicMock(return_value=mock_dest_search)

        # Mock the _add_entities_cypher method
        mock_cypher = "MATCH (n) RETURN n"
        mock_params = {"source_id": 123, "destination_id": 456}
        self.memory_graph._add_entities_cypher = MagicMock(return_value=(mock_cypher, mock_params))

        # Mock the graph.query result
        mock_query_result = [{"source": "alice", "relationship": "knows", "target": "bob"}]
        self.mock_graph.query.return_value = mock_query_result

        # Call the _add_entities method
        result = self.memory_graph._add_entities(to_be_added, self.user_id, entity_type_map)

        # Verify the method calls
        self.assertEqual(self.mock_embedding_model.embed.call_count, 2)
        self.memory_graph._search_source_node.assert_called_once_with(mock_embedding, self.user_id, threshold=0.9)
        self.memory_graph._search_destination_node.assert_called_once_with(mock_embedding, self.user_id, threshold=0.9)
        self.memory_graph._add_entities_cypher.assert_called_once()
        self.mock_graph.query.assert_called_once_with(mock_cypher, params=mock_params)

        # Check the result
        self.assertEqual(result, [mock_query_result])

    def test_delete_entities(self):
        """Test the _delete_entities method."""
        # Mock data
        to_be_deleted = [{"source": "alice", "relationship": "knows", "destination": "bob"}]

        # Mock the _delete_entities_cypher method
        mock_cypher = "MATCH (n) RETURN n"
        mock_params = {"source_name": "alice", "dest_name": "bob", "user_id": self.user_id}
        self.memory_graph._delete_entities_cypher = MagicMock(return_value=(mock_cypher, mock_params))

        # Mock the graph.query result
        mock_query_result = [{"source": "alice", "relationship": "knows", "target": "bob"}]
        self.mock_graph.query.return_value = mock_query_result

        # Call the _delete_entities method
        result = self.memory_graph._delete_entities(to_be_deleted, self.user_id)

        # Verify the method calls
        self.memory_graph._delete_entities_cypher.assert_called_once_with("alice", "bob", "knows", self.user_id)
        self.mock_graph.query.assert_called_once_with(mock_cypher, params=mock_params)

        # Check the result
        self.assertEqual(result, [mock_query_result])


if __name__ == "__main__":
    unittest.main()
