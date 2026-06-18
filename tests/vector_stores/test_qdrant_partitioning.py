"""Tests for Qdrant partitioning support (task_02 / ADR-002).

Covers the Fase 2 extensions to the Qdrant provider:
- ``project`` indexed as a tenant key (``is_tenant=True``);
- the new payload indexes (``type``, ``hash`` keyword; ``created_at`` datetime);
- local mode still skips index creation;
- collection creation passes cluster topology (shard/replication/custom sharding)
  only when configured, preserving the single-node call shape;
- ``search``/``insert`` route to a dedicated shard key when provided;
- ``create_shard_key`` helper for tenant promotion.

All tests mock ``QdrantClient`` — no live Qdrant required.
"""

import unittest
import uuid
from unittest.mock import MagicMock

from qdrant_client import QdrantClient, models

from mem0.configs.vector_stores.qdrant import QdrantConfig
from mem0.vector_stores.qdrant import Qdrant


class TestQdrantPartitioning(unittest.TestCase):
    def setUp(self):
        self.client_mock = MagicMock(spec=QdrantClient)
        self.client_mock.get_collections.return_value = MagicMock(collections=[])
        self.qdrant = Qdrant(
            collection_name="test_collection",
            embedding_model_dims=128,
            client=self.client_mock,
        )

    # ------------------------------------------------------------------ #
    # Payload indexes
    # ------------------------------------------------------------------ #
    def test_project_indexed_as_tenant(self):
        self.client_mock.create_payload_index.reset_mock()
        self.qdrant._create_filter_indexes()

        project_calls = [
            c for c in self.client_mock.create_payload_index.call_args_list
            if c.kwargs.get("field_name") == "project"
        ]
        self.assertEqual(len(project_calls), 1)
        schema = project_calls[0].kwargs["field_schema"]
        self.assertIsInstance(schema, models.KeywordIndexParams)
        self.assertTrue(schema.is_tenant)

    def test_new_and_existing_payload_indexes(self):
        self.client_mock.create_payload_index.reset_mock()
        self.qdrant._create_filter_indexes()

        indexed = {
            c.kwargs.get("field_name"): c.kwargs.get("field_schema")
            for c in self.client_mock.create_payload_index.call_args_list
        }
        # New Fase 2 indexes.
        self.assertEqual(indexed.get("type"), "keyword")
        self.assertEqual(indexed.get("hash"), "keyword")
        self.assertEqual(indexed.get("created_at"), "datetime")
        # Pre-existing identity indexes preserved.
        for field in ("user_id", "agent_id", "run_id", "actor_id"):
            self.assertEqual(indexed.get(field), "keyword")

    def test_local_mode_skips_index_creation(self):
        self.qdrant.is_local = True
        self.client_mock.create_payload_index.reset_mock()
        self.qdrant._create_filter_indexes()
        self.client_mock.create_payload_index.assert_not_called()

    # ------------------------------------------------------------------ #
    # Cluster topology on create_collection
    # ------------------------------------------------------------------ #
    def test_create_col_single_node_omits_cluster_kwargs(self):
        kwargs = self.client_mock.create_collection.call_args.kwargs
        self.assertNotIn("shard_number", kwargs)
        self.assertNotIn("replication_factor", kwargs)
        self.assertNotIn("sharding_method", kwargs)

    def test_create_col_with_cluster_topology(self):
        client = MagicMock(spec=QdrantClient)
        client.get_collections.return_value = MagicMock(collections=[])
        Qdrant(
            collection_name="c",
            embedding_model_dims=128,
            client=client,
            shard_number=6,
            replication_factor=2,
            custom_sharding=True,
        )
        kwargs = client.create_collection.call_args.kwargs
        self.assertEqual(kwargs["shard_number"], 6)
        self.assertEqual(kwargs["replication_factor"], 2)
        self.assertEqual(kwargs["sharding_method"], models.ShardingMethod.CUSTOM)

    # ------------------------------------------------------------------ #
    # Shard-key routing
    # ------------------------------------------------------------------ #
    def test_search_passes_shard_key_selector(self):
        self.client_mock.query_points.return_value = MagicMock(points=[])
        self.qdrant.search(
            query="", vectors=[[0.1, 0.2]], top_k=3,
            filters={"project": "big"}, shard_key_selector="big",
        )
        kwargs = self.client_mock.query_points.call_args.kwargs
        self.assertEqual(kwargs["shard_key_selector"], "big")

    def test_search_without_shard_key_selector_omits_it(self):
        self.client_mock.query_points.return_value = MagicMock(points=[])
        self.qdrant.search(query="", vectors=[[0.1, 0.2]], top_k=3)
        kwargs = self.client_mock.query_points.call_args.kwargs
        self.assertNotIn("shard_key_selector", kwargs)

    def test_insert_routes_to_shard_key(self):
        self.qdrant.insert(
            vectors=[[0.1, 0.2]], payloads=[{"data": "x"}],
            ids=[str(uuid.uuid4())], shard_key="big",
        )
        kwargs = self.client_mock.upsert.call_args.kwargs
        self.assertEqual(kwargs["shard_key_selector"], "big")

    def test_insert_without_shard_key_omits_selector(self):
        self.qdrant.insert(
            vectors=[[0.1, 0.2]], payloads=[{"data": "x"}], ids=[str(uuid.uuid4())],
        )
        kwargs = self.client_mock.upsert.call_args.kwargs
        self.assertNotIn("shard_key_selector", kwargs)

    def test_create_shard_key(self):
        self.qdrant.create_shard_key("big")
        self.client_mock.create_shard_key.assert_called_once_with("test_collection", "big")


class TestQdrantConfigClusterFields(unittest.TestCase):
    def test_config_accepts_cluster_fields(self):
        cfg = QdrantConfig(
            path="/tmp/qdrant_test",
            shard_number=6,
            replication_factor=2,
            custom_sharding=True,
        )
        self.assertEqual(cfg.shard_number, 6)
        self.assertEqual(cfg.replication_factor, 2)
        self.assertTrue(cfg.custom_sharding)

    def test_config_cluster_fields_default_off(self):
        cfg = QdrantConfig(path="/tmp/qdrant_test")
        self.assertIsNone(cfg.shard_number)
        self.assertIsNone(cfg.replication_factor)
        self.assertFalse(cfg.custom_sharding)


if __name__ == "__main__":
    unittest.main()
