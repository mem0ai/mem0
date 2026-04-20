import unittest
from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, patch

from mem0.memory.nebulagraph_memory import MemoryGraph


def make_config(base_collection=None, graph_collection=None):
    vector_store_config = SimpleNamespace(
        collection_name=base_collection,
        host="localhost",
        port=9200,
        user="user",
        password="pass",
    )
    graph_store_config = SimpleNamespace(
        graph_address="localhost:9669",
        username="root",
        password="nebula",
        space="mem0_space",
        collection_name=graph_collection,
    )
    config = SimpleNamespace(
        embedder=SimpleNamespace(provider="openai", config={}),
        llm=SimpleNamespace(provider="openai", config={}),
        vector_store=SimpleNamespace(provider="elasticsearch", config=vector_store_config),
        graph_store=SimpleNamespace(
            provider="nebulagraph",
            config=graph_store_config,
            threshold=0.7,
            llm=None,
            custom_prompt=None,
        ),
    )
    return config


class TestNebulaGraphMemory(unittest.TestCase):
    def setUp(self):
        self.config = make_config(base_collection="mem0_vectors", graph_collection="mem0_graph_vectors")

        self.mock_embedding_model = MagicMock()
        self.mock_llm = MagicMock()
        self.mock_vector_store = MagicMock()

        self.init_patcher = patch("mem0.memory.nebulagraph_memory.MemoryGraph._init_nebula_connection")
        self.schema_patcher = patch("mem0.memory.nebulagraph_memory.MemoryGraph._create_schema")
        self.embedder_patcher = patch("mem0.memory.nebulagraph_memory.EmbedderFactory")
        self.llm_patcher = patch("mem0.memory.nebulagraph_memory.LlmFactory")
        self.vector_patcher = patch("mem0.memory.nebulagraph_memory.VectorStoreFactory")

        self.mock_init = self.init_patcher.start()
        self.mock_schema = self.schema_patcher.start()
        self.mock_embedder_factory = self.embedder_patcher.start()
        self.mock_llm_factory = self.llm_patcher.start()
        self.mock_vector_factory = self.vector_patcher.start()

        self.mock_embedder_factory.create.return_value = self.mock_embedding_model
        self.mock_llm_factory.create.return_value = self.mock_llm
        self.mock_vector_factory.create.return_value = self.mock_vector_store

        self.memory_graph = MemoryGraph(self.config)

        self.user_id = "test_user"
        self.filters = {"user_id": self.user_id}

    def tearDown(self):
        self.init_patcher.stop()
        self.schema_patcher.stop()
        self.embedder_patcher.stop()
        self.llm_patcher.stop()
        self.vector_patcher.stop()

    def test_collection_name_variants(self):
        created = []

        def capture_create(provider, cfg):
            created.append(cfg)
            return MagicMock()

        self.mock_vector_factory.create.side_effect = capture_create

        # 1) graph_store.config.collection_name set
        config1 = make_config(base_collection="base", graph_collection="custom_graph_collection")
        MemoryGraph(config1)
        self.assertEqual(created[-1].collection_name, "custom_graph_collection")

        # 2) base collection set, graph collection None
        config2 = make_config(base_collection="base", graph_collection=None)
        MemoryGraph(config2)
        self.assertEqual(created[-1].collection_name, "base_nebulagraph_vectors")

        # 3) neither set
        config3 = make_config(base_collection=None, graph_collection=None)
        MemoryGraph(config3)
        self.assertEqual(created[-1].collection_name, "mem0_nebulagraph_vectors")

    def test_add_method_calls(self):
        self.memory_graph._retrieve_nodes_from_data = MagicMock(return_value={"alice": "person"})
        self.memory_graph._establish_nodes_relations_from_data = MagicMock(
            return_value=[{"source": "alice", "relationship": "likes", "destination": "pizza"}]
        )
        self.memory_graph._search_graph_db = MagicMock(return_value=[])
        self.memory_graph._get_delete_entities_from_search_output = MagicMock(return_value=[])
        self.memory_graph._delete_entities = MagicMock(return_value=[])
        self.memory_graph._add_entities = MagicMock(
            return_value=[{"source": "alice", "relationship": "likes", "target": "pizza"}]
        )

        result = self.memory_graph.add("Alice likes pizza", self.filters)

        self.memory_graph._retrieve_nodes_from_data.assert_called_once_with("Alice likes pizza", self.filters)
        self.memory_graph._establish_nodes_relations_from_data.assert_called_once()
        self.memory_graph._search_graph_db.assert_called_once()
        self.memory_graph._get_delete_entities_from_search_output.assert_called_once()
        self.memory_graph._delete_entities.assert_called_once()
        self.memory_graph._add_entities.assert_called_once()

        self.assertIn("deleted_entities", result)
        self.assertIn("added_entities", result)

    def test_search_method(self):
        self.memory_graph._retrieve_nodes_from_data = MagicMock(return_value={"alice": "person"})
        mock_search_results = [
            {"source": "alice", "relationship": "likes", "destination": "pizza"},
            {"source": "alice", "relationship": "likes", "destination": "sushi"},
        ]
        self.memory_graph._search_graph_db = MagicMock(return_value=mock_search_results)

        with patch("mem0.memory.nebulagraph_memory.BM25Okapi") as mock_bm25:
            mock_bm25_instance = MagicMock()
            mock_bm25.return_value = mock_bm25_instance
            mock_bm25_instance.get_top_n.return_value = [
                ["alice", "likes", "pizza"],
                ["alice", "likes", "sushi"],
            ]

            result = self.memory_graph.search("what does alice like?", self.filters, limit=5)

        self.memory_graph._retrieve_nodes_from_data.assert_called_once_with("what does alice like?", self.filters)
        self.memory_graph._search_graph_db.assert_called_once_with(
            node_list=["alice"], filters=self.filters, embedding_cache=ANY
        )
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["source"], "alice")
        self.assertEqual(result[0]["relationship"], "likes")
        self.assertEqual(result[0]["destination"], "pizza")

    def test_search_graph_db_uses_top_k_for_vector_store(self):
        self.memory_graph.embedding_model.embed.return_value = [0.1]
        self.memory_graph.vector_store.search.return_value = [SimpleNamespace(id="node-1", score=0.9)]
        self.memory_graph._execute_query = MagicMock(
            return_value=[{"source": "alice", "relationship": "likes", "destination": "pizza"}]
        )

        result = self.memory_graph._search_graph_db(["alice"], self.filters, embedding_cache={})

        self.memory_graph.vector_store.search.assert_called_once_with(
            query="",
            vectors=[0.1],
            top_k=self.memory_graph.vector_store_limit,
            filters=self.filters,
        )
        self.assertEqual(result, [{"source": "alice", "relationship": "likes", "destination": "pizza"}])

    def test_add_entities_when_nodes_not_found_creates_new_nodes(self):
        self.memory_graph.embedding_model.embed.return_value = [0.1]
        self.memory_graph._search_node_in_vector_store = MagicMock(side_effect=[None, None])
        self.memory_graph._node_exists = MagicMock(return_value=True)
        # Returns same id for both source and dest, triggering the self-loop guard (3rd call)
        self.memory_graph._create_node = MagicMock(side_effect=["new_source", "new_source", "new_dest"])
        self.memory_graph._execute_query = MagicMock(return_value=[])
        self.memory_graph._execute_raw_query = MagicMock(return_value=[])

        to_be_added = [{"source": "alice", "relationship": "likes", "destination": "pizza"}]
        entity_type_map = {"alice": "__User__", "pizza": "__User__"}

        result = self.memory_graph._add_entities(to_be_added, self.filters, entity_type_map, embedding_cache={})

        self.assertEqual(result, [{"source": "alice", "relationship": "likes", "target": "pizza"}])
        # _create_node called 3 times: source (not found → new), dest (not found → new),
        # and dest again (self-loop guard: source_id == dest_id)
        self.assertEqual(self.memory_graph._create_node.call_count, 3)
        self.memory_graph._execute_raw_query.assert_called_once()
        self.assertIn("INSERT EDGE CONNECTED_TO", self.memory_graph._execute_raw_query.call_args[0][0])

    def test_get_all_method(self):
        self.memory_graph._execute_query = MagicMock(
            return_value=[
                {"source": "alice", "relationship": "likes", "target": "pizza"},
                {"source": "alice", "relationship": "likes", "target": "sushi"},
            ]
        )

        result = self.memory_graph.get_all(self.filters, limit=10)

        self.memory_graph._execute_query.assert_called_once()
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["source"], "alice")
        self.assertEqual(result[0]["relationship"], "likes")
        self.assertEqual(result[0]["target"], "pizza")

    def test_search_node_in_vector_store_uses_top_k_limit(self):
        self.memory_graph.vector_store.search.return_value = [SimpleNamespace(id="node-1", score=0.9)]

        result = self.memory_graph._search_node_in_vector_store([0.1], self.filters)

        self.memory_graph.vector_store.search.assert_called_once_with(
            query="",
            vectors=[0.1],
            top_k=self.memory_graph.vector_store_limit,
            filters=self.filters,
        )
        self.assertEqual(result, "node-1")

    def test_search_node_in_vector_store_returns_highest_scoring_threshold_match(self):
        self.memory_graph.vector_store.search.return_value = [
            SimpleNamespace(id="node-mid", score=0.82),
            SimpleNamespace(id="node-best", score=0.95),
            SimpleNamespace(id="node-low-score", score=0.4),
        ]

        result = self.memory_graph._search_node_in_vector_store([0.1], self.filters)

        self.assertEqual(result, "node-best")

    def test_delete_all_method(self):
        self.memory_graph._execute_raw_query = MagicMock(return_value=[])
        self.memory_graph.vector_store.list.return_value = [
            SimpleNamespace(id="vec1"),
            SimpleNamespace(id="vec2"),
        ]

        self.memory_graph.delete_all(self.filters)

        self.memory_graph.vector_store.list.assert_called_once_with(filters=self.filters)
        self.assertEqual(self.memory_graph.vector_store.delete.call_count, 2)
        self.memory_graph._execute_raw_query.assert_called_once()
        self.assertIn("DELETE VERTEX", self.memory_graph._execute_raw_query.call_args[0][0])

    def test_reset_method(self):
        self.memory_graph._execute_raw_query = MagicMock(return_value=[])

        self.memory_graph.reset()

        self.memory_graph.vector_store.reset.assert_called_once()
        self.memory_graph._execute_raw_query.assert_called_once()

    def test_add_entities_self_loop_guard(self):
        self.memory_graph.embedding_model.embed.return_value = [0.1]
        self.memory_graph._search_node_in_vector_store = MagicMock(side_effect=["same", "same"])
        self.memory_graph._node_exists = MagicMock(return_value=True)
        self.memory_graph._create_node = MagicMock(return_value="new_dest")
        self.memory_graph._execute_query = MagicMock(return_value=[])
        self.memory_graph._execute_raw_query = MagicMock(return_value=[])

        to_be_added = [{"source": "alice", "relationship": "likes", "destination": "pizza"}]
        entity_type_map = {"alice": "__User__", "pizza": "__User__"}

        result = self.memory_graph._add_entities(to_be_added, self.filters, entity_type_map, embedding_cache={})

        self.assertEqual(result, [{"source": "alice", "relationship": "likes", "target": "pizza"}])
        self.memory_graph._create_node.assert_called_once()
        self.memory_graph._execute_raw_query.assert_called_once()
        self.assertIn("INSERT EDGE CONNECTED_TO", self.memory_graph._execute_raw_query.call_args[0][0])


if __name__ == "__main__":
    unittest.main()
