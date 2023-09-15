# ruff: noqa: E501

import unittest
from unittest.mock import patch

from chromadb.config import Settings

from embedchain import App
from embedchain.config import AppConfig, ChromaDbConfig
from embedchain.vectordb.chroma import ChromaDB


class TestChromaDbHosts(unittest.TestCase):
    def test_init_with_host_and_port(self):
        """
        Test if the `ChromaDB` instance is initialized with the correct host and port values.
        """
        host = "test-host"
        port = "1234"
        config = ChromaDbConfig(host=host, port=port)

        db = ChromaDB(config=config)
        settings = db.client.get_settings()
        self.assertEqual(settings.chroma_server_host, host)
        self.assertEqual(settings.chroma_server_http_port, port)

    def test_init_with_basic_auth(self):
        host = "test-host"
        port = "1234"

        chroma_auth_settings = {
            "chroma_client_auth_provider": "chromadb.auth.basic.BasicAuthClientProvider",
            "chroma_client_auth_credentials": "admin:admin",
        }

        config = ChromaDbConfig(host=host, port=port, chroma_settings=chroma_auth_settings)
        db = ChromaDB(config=config)
        settings = db.client.get_settings()
        self.assertEqual(settings.chroma_server_host, host)
        self.assertEqual(settings.chroma_server_http_port, port)
        self.assertEqual(settings.chroma_client_auth_provider, chroma_auth_settings["chroma_client_auth_provider"])
        self.assertEqual(
            settings.chroma_client_auth_credentials, chroma_auth_settings["chroma_client_auth_credentials"]
        )


# Review this test
class TestChromaDbHostsInit(unittest.TestCase):
    @patch("embedchain.vectordb.chroma.chromadb.Client")
    def test_app_init_with_host_and_port(self, mock_client):
        """
        Test if the `App` instance is initialized with the correct host and port values.
        """
        host = "test-host"
        port = "1234"

        config = AppConfig(collect_metrics=False)
        chromadb_config = ChromaDbConfig(host=host, port=port)

        _app = App(config, chromadb_config=chromadb_config)

        called_settings: Settings = mock_client.call_args[0][0]

        self.assertEqual(called_settings.chroma_server_host, host)
        self.assertEqual(called_settings.chroma_server_http_port, port)


class TestChromaDbHostsNone(unittest.TestCase):
    @patch("embedchain.vectordb.chroma.chromadb.Client")
    def test_init_with_host_and_port_none(self, mock_client):
        """
        Test if the `App` instance is initialized without default hosts and ports.
        """

        _app = App(config=AppConfig(collect_metrics=False))

        called_settings: Settings = mock_client.call_args[0][0]
        self.assertEqual(called_settings.chroma_server_host, None)
        self.assertEqual(called_settings.chroma_server_http_port, None)


class TestChromaDbHostsLoglevel(unittest.TestCase):
    @patch("embedchain.vectordb.chroma.chromadb.Client")
    def test_init_with_host_and_port_log_level(self, mock_client):
        """
        Test if the `App` instance is initialized without a config that does not contain default hosts and ports.
        """

        _app = App(config=AppConfig(collect_metrics=False))

        self.assertEqual(mock_client.call_args[0][0].chroma_server_host, None)
        self.assertEqual(mock_client.call_args[0][0].chroma_server_http_port, None)


class TestChromaDbDuplicateHandling:
    chroma_config = ChromaDbConfig(allow_reset=True)
    app_config = AppConfig(collection_name=False, collect_metrics=False)
    app_with_settings = App(config=app_config, chromadb_config=chroma_config)

    def test_duplicates_throw_warning(self, caplog):
        """
        Test that add duplicates throws an error.
        """
        # Start with a clean app
        self.app_with_settings.reset()

        app = App(config=AppConfig(collect_metrics=False))
        app.db.collection.add(embeddings=[[0, 0, 0]], ids=["0"])
        app.db.collection.add(embeddings=[[0, 0, 0]], ids=["0"])
        assert "Insert of existing embedding ID: 0" in caplog.text
        assert "Add of existing embedding ID: 0" in caplog.text

    def test_duplicates_collections_no_warning(self, caplog):
        """
        Test that different collections can have duplicates.
        """
        # NOTE: Not part of the TestChromaDbCollection because `unittest.TestCase` doesn't have caplog.

        # Start with a clean app
        self.app_with_settings.reset()

        app = App(config=AppConfig(collect_metrics=False))
        app.set_collection_name("test_collection_1")
        app.db.collection.add(embeddings=[[0, 0, 0]], ids=["0"])
        app.set_collection_name("test_collection_2")
        app.db.collection.add(embeddings=[[0, 0, 0]], ids=["0"])
        assert "Insert of existing embedding ID: 0" not in caplog.text  # not
        assert "Add of existing embedding ID: 0" not in caplog.text  # not


class TestChromaDbCollection(unittest.TestCase):
    chroma_config = ChromaDbConfig(allow_reset=True)
    app_config = AppConfig(collection_name=False, collect_metrics=False)
    app_with_settings = App(config=app_config, chromadb_config=chroma_config)

    def test_init_with_default_collection(self):
        """
        Test if the `App` instance is initialized with the correct default collection name.
        """
        app = App(config=AppConfig(collect_metrics=False))

        self.assertEqual(app.db.collection.name, "embedchain_store")

    def test_init_with_custom_collection(self):
        """
        Test if the `App` instance is initialized with the correct custom collection name.
        """
        config = AppConfig(collect_metrics=False)
        app = App(config=config)
        app.set_collection_name(name="test_collection")

        self.assertEqual(app.db.collection.name, "test_collection")

    def test_set_collection_name(self):
        """
        Test if the `App` collection is correctly switched using the `set_collection_name` method.
        """
        app = App(config=AppConfig(collect_metrics=False))
        app.set_collection_name("test_collection")

        self.assertEqual(app.db.collection.name, "test_collection")

    def test_changes_encapsulated(self):
        """
        Test that changes to one collection do not affect the other collection
        """
        # Start with a clean app
        self.app_with_settings.reset()

        app = App(config=AppConfig(collect_metrics=False))
        app.set_collection_name("test_collection_1")
        # Collection should be empty when created
        self.assertEqual(app.db.count(), 0)

        app.db.collection.add(embeddings=[0, 0, 0], ids=["0"])
        # After adding, should contain one item
        self.assertEqual(app.db.count(), 1)

        app.set_collection_name("test_collection_2")
        # New collection is empty
        self.assertEqual(app.db.count(), 0)

        # Adding to new collection should not effect existing collection
        app.db.collection.add(embeddings=[0, 0, 0], ids=["0"])
        app.set_collection_name("test_collection_1")
        # Should still be 1, not 2.
        self.assertEqual(app.db.count(), 1)

    def test_collections_are_persistent(self):
        """
        Test that a collection can be picked up later.
        """
        # Start with a clean app
        self.app_with_settings.reset()

        app = App(config=AppConfig(collect_metrics=False))
        app.set_collection_name("test_collection_1")
        app.db.collection.add(embeddings=[[0, 0, 0]], ids=["0"])
        del app

        app = App(config=AppConfig(collect_metrics=False))
        app.set_collection_name("test_collection_1")
        self.assertEqual(app.db.count(), 1)

    def test_parallel_collections(self):
        """
        Test that two apps can have different collections open in parallel.
        Switching the names will allow instant access to the collection of
        the other app.
        """
        # Start clean
        self.app_with_settings.reset()

        # Create two apps
        app1 = App(AppConfig(collection_name="test_collection_1", collect_metrics=False))
        app2 = App(AppConfig(collection_name="test_collection_2", collect_metrics=False))

        # app2 has been created last, but adding to app1 will still write to collection 1.
        app1.db.collection.add(embeddings=[0, 0, 0], ids=["0"])
        self.assertEqual(app1.db.count(), 1)
        self.assertEqual(app2.db.count(), 0)

        # Add data
        app1.db.collection.add(embeddings=[[0, 0, 0], [1, 1, 1]], ids=["1", "2"])
        app2.db.collection.add(embeddings=[0, 0, 0], ids=["0"])

        # Swap names and test
        app1.set_collection_name("test_collection_2")
        self.assertEqual(app1.count(), 1)
        app2.set_collection_name("test_collection_1")
        self.assertEqual(app2.count(), 3)

    def test_ids_share_collections(self):
        """
        Different ids should still share collections.
        """
        # Start clean
        self.app_with_settings.reset()

        # Create two apps
        app1 = App(AppConfig(id="new_app_id_1", collect_metrics=False))
        app1.set_collection_name("one_collection")
        app2 = App(AppConfig(id="new_app_id_2", collect_metrics=False))
        app2.set_collection_name("one_collection")

        # Add data
        app1.db.collection.add(embeddings=[[0, 0, 0], [1, 1, 1]], ids=["0", "1"])
        app2.db.collection.add(embeddings=[0, 0, 0], ids=["2"])

        # Both should have the same collection
        self.assertEqual(app1.count(), 3)
        self.assertEqual(app2.count(), 3)

    def test_reset(self):
        """
        Resetting should hit all collections and ids.
        """
        # Start clean
        self.app_with_settings.reset()

        # Create four apps.
        # app1, which we are about to reset, shares an app with one, and an id with the other, none with the last.
        app1 = App(AppConfig(id="new_app_id_1", collect_metrics=False), chromadb_config=self.chroma_config)
        app1.set_collection_name("one_collection")
        app2 = App(AppConfig(id="new_app_id_2", collect_metrics=False))
        app2.set_collection_name("one_collection")
        app3 = App(AppConfig(id="new_app_id_1", collect_metrics=False))
        app3.set_collection_name("three_collection")
        app4 = App(AppConfig(id="new_app_id_4", collect_metrics=False))
        app4.set_collection_name("four_collection")

        # Each one of them get data
        app1.db.collection.add(embeddings=[0, 0, 0], ids=["1"])
        app2.db.collection.add(embeddings=[0, 0, 0], ids=["2"])
        app3.db.collection.add(embeddings=[0, 0, 0], ids=["3"])
        app4.db.collection.add(embeddings=[0, 0, 0], ids=["4"])

        # Resetting the first one should reset them all.
        app1.reset()

        # Reinstantiate app2-4, app1 doesn't have to be reinstantiated (PR #319)
        app2 = App(AppConfig(collection_name="one_collection", id="new_app_id_2", collect_metrics=False))
        app3 = App(AppConfig(collection_name="three_collection", id="new_app_id_3", collect_metrics=False))
        app4 = App(AppConfig(collection_name="four_collection", id="new_app_id_3", collect_metrics=False))

        # All should be empty
        self.assertEqual(app1.count(), 0)
        self.assertEqual(app2.count(), 0)
        self.assertEqual(app3.count(), 0)
        self.assertEqual(app4.count(), 0)
