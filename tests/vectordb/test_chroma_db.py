# ruff: noqa: E501

import unittest
from unittest.mock import patch

from chromadb.config import Settings

from embedchain import App
from embedchain.config import AppConfig
from embedchain.vectordb.chroma_db import ChromaDB, chromadb


class TestChromaDbHosts(unittest.TestCase):
    def test_init_with_host_and_port(self):
        """
        Test if the `ChromaDB` instance is initialized with the correct host and port values.
        """
        host = "test-host"
        port = "1234"

        with patch.object(chromadb, "HttpClient") as mock_client:
            _db = ChromaDB(host=host, port=port, embedding_fn=len)

        expected_settings = Settings(
            chroma_server_host="test-host",
            chroma_server_http_port="1234",
        )

        mock_client.assert_called_once_with(expected_settings)


# Review this test
class TestChromaDbHostsInit(unittest.TestCase):
    @patch("embedchain.vectordb.chroma_db.chromadb.Client")
    def test_init_with_host_and_port(self, mock_client):
        """
        Test if the `App` instance is initialized with the correct host and port values.
        """
        host = "test-host"
        port = "1234"

        config = AppConfig(host=host, port=port, collect_metrics=False)

        _app = App(config)

        # self.assertEqual(mock_client.call_args[0][0].chroma_server_host, host)
        # self.assertEqual(mock_client.call_args[0][0].chroma_server_http_port, port)


class TestChromaDbHostsNone(unittest.TestCase):
    @patch("embedchain.vectordb.chroma_db.chromadb.Client")
    def test_init_with_host_and_port(self, mock_client):
        """
        Test if the `App` instance is initialized without default hosts and ports.
        """

        _app = App(config=AppConfig(collect_metrics=False))

        self.assertEqual(mock_client.call_args[0][0].chroma_server_host, None)
        self.assertEqual(mock_client.call_args[0][0].chroma_server_http_port, None)


class TestChromaDbHostsLoglevel(unittest.TestCase):
    @patch("embedchain.vectordb.chroma_db.chromadb.Client")
    def test_init_with_host_and_port(self, mock_client):
        """
        Test if the `App` instance is initialized without a config that does not contain default hosts and ports.
        """
        config = AppConfig(log_level="DEBUG")

        _app = App(config=AppConfig(collect_metrics=False))

        self.assertEqual(mock_client.call_args[0][0].chroma_server_host, None)
        self.assertEqual(mock_client.call_args[0][0].chroma_server_http_port, None)


class TestChromaDbDuplicateHandling:
    def test_duplicates_throw_warning(self, caplog):
        """
        Test that add duplicates throws an error.
        """
        # Start with a clean app
        App().reset()

        app = App(config=AppConfig(collect_metrics=False))
        app.collection.add(embeddings=[[0, 0, 0]], ids=["0"])
        app.collection.add(embeddings=[[0, 0, 0]], ids=["0"])
        assert "Insert of existing embedding ID: 0" in caplog.text
        assert "Add of existing embedding ID: 0" in caplog.text

    def test_duplicates_collections_no_warning(self, caplog):
        """
        Test that different collections can have duplicates.
        """
        # NOTE: Not part of the TestChromaDbCollection because `unittest.TestCase` doesn't have caplog.

        # Start with a clean app
        App().reset()

        app = App(config=AppConfig(collect_metrics=False))
        app.set_collection("test_collection_1")
        app.collection.add(embeddings=[[0, 0, 0]], ids=["0"])
        app.set_collection("test_collection_2")
        app.collection.add(embeddings=[[0, 0, 0]], ids=["0"])
        assert "Insert of existing embedding ID: 0" not in caplog.text  # not
        assert "Add of existing embedding ID: 0" not in caplog.text  # not


class TestChromaDbCollection(unittest.TestCase):
    def test_init_with_default_collection(self):
        """
        Test if the `App` instance is initialized with the correct default collection name.
        """
        app = App(config=AppConfig(collect_metrics=False))

        self.assertEqual(app.collection.name, "embedchain_store")

    def test_init_with_custom_collection(self):
        """
        Test if the `App` instance is initialized with the correct custom collection name.
        """
        config = AppConfig(collection_name="test_collection", collect_metrics=False)
        app = App(config)

        self.assertEqual(app.collection.name, "test_collection")

    def test_set_collection(self):
        """
        Test if the `App` collection is correctly switched using the `set_collection` method.
        """
        app = App(config=AppConfig(collect_metrics=False))
        app.set_collection("test_collection")

        self.assertEqual(app.collection.name, "test_collection")

    def test_changes_encapsulated(self):
        """
        Test that changes to one collection do not affect the other collection
        """
        # Start with a clean app
        App().reset()

        app = App(config=AppConfig(collect_metrics=False))
        app.set_collection("test_collection_1")
        # Collection should be empty when created
        self.assertEqual(app.count(), 0)

        app.collection.add(embeddings=[0, 0, 0], ids=["0"])
        # After adding, should contain one item
        self.assertEqual(app.count(), 1)

        app.set_collection("test_collection_2")
        # New collection is empty
        self.assertEqual(app.count(), 0)

        # Adding to new collection should not effect existing collection
        app.collection.add(embeddings=[0, 0, 0], ids=["0"])
        app.set_collection("test_collection_1")
        # Should still be 1, not 2.
        self.assertEqual(app.count(), 1)

    def test_collections_are_persistent(self):
        """
        Test that a collection can be picked up later.
        """
        # Start with a clean app
        App().reset()

        app = App(config=AppConfig(collect_metrics=False))
        app.set_collection("test_collection_1")
        app.collection.add(embeddings=[[0, 0, 0]], ids=["0"])
        del app

        app = App(config=AppConfig(collect_metrics=False))
        app.set_collection("test_collection_1")
        self.assertEqual(app.count(), 1)

    def test_parallel_collections(self):
        """
        Test that two apps can have different collections open in parallel.
        Switching the names will allow instant access to the collection of
        the other app.
        """
        # Start clean
        App().reset()

        # Create two apps
        app1 = App(AppConfig(collection_name="test_collection_1", collect_metrics=False))
        app2 = App(AppConfig(collection_name="test_collection_2", collect_metrics=False))

        # app2 has been created last, but adding to app1 will still write to collection 1.
        app1.collection.add(embeddings=[0, 0, 0], ids=["0"])
        self.assertEqual(app1.count(), 1)
        self.assertEqual(app2.count(), 0)

        # Add data
        app1.collection.add(embeddings=[[0, 0, 0], [1, 1, 1]], ids=["1", "2"])
        app2.collection.add(embeddings=[0, 0, 0], ids=["0"])

        # Swap names and test
        app1.set_collection("test_collection_2")
        self.assertEqual(app1.count(), 1)
        app2.set_collection("test_collection_1")
        self.assertEqual(app2.count(), 3)

    def test_ids_share_collections(self):
        """
        Different ids should still share collections.
        """
        # Start clean
        App().reset()

        # Create two apps
        app1 = App(AppConfig(collection_name="one_collection", id="new_app_id_1", collect_metrics=False))
        app2 = App(AppConfig(collection_name="one_collection", id="new_app_id_2", collect_metrics=False))

        # Add data
        app1.collection.add(embeddings=[[0, 0, 0], [1, 1, 1]], ids=["0", "1"])
        app2.collection.add(embeddings=[0, 0, 0], ids=["2"])

        # Both should have the same collection
        self.assertEqual(app1.count(), 3)
        self.assertEqual(app2.count(), 3)

    def test_reset(self):
        """
        Resetting should hit all collections and ids.
        """
        # Start clean
        App().reset()

        # Create four apps.
        # app1, which we are about to reset, shares an app with one, and an id with the other, none with the last.
        app1 = App(AppConfig(collection_name="one_collection", id="new_app_id_1", collect_metrics=False))
        app2 = App(AppConfig(collection_name="one_collection", id="new_app_id_2", collect_metrics=False))
        app3 = App(AppConfig(collection_name="three_collection", id="new_app_id_1", collect_metrics=False))
        app4 = App(AppConfig(collection_name="four_collection", id="new_app_id_4", collect_metrics=False))

        # Each one of them get data
        app1.collection.add(embeddings=[0, 0, 0], ids=["1"])
        app2.collection.add(embeddings=[0, 0, 0], ids=["2"])
        app3.collection.add(embeddings=[0, 0, 0], ids=["3"])
        app4.collection.add(embeddings=[0, 0, 0], ids=["4"])

        # Resetting the first one should reset them all.
        app1.reset()

        # Reinstantiate them
        app1 = App(AppConfig(collection_name="one_collection", id="new_app_id_1", collect_metrics=False))
        app2 = App(AppConfig(collection_name="one_collection", id="new_app_id_2", collect_metrics=False))
        app3 = App(AppConfig(collection_name="three_collection", id="new_app_id_3", collect_metrics=False))
        app4 = App(AppConfig(collection_name="four_collection", id="new_app_id_3", collect_metrics=False))

        # All should be empty
        self.assertEqual(app1.count(), 0)
        self.assertEqual(app2.count(), 0)
        self.assertEqual(app3.count(), 0)
        self.assertEqual(app4.count(), 0)
