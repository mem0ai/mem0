import os
import pytest
from unittest.mock import patch

from chromadb.config import Settings
from embedchain import App
from embedchain.config import AppConfig, ChromaDbConfig
from embedchain.vectordb.chroma import ChromaDB

os.environ["OPENAI_API_KEY"] = "xxx"


@pytest.fixture
def chroma_db():
    return ChromaDB(config=ChromaDbConfig(host="test-host", port="1234"))


@pytest.fixture
def app_with_settings():
    chroma_config = ChromaDbConfig(allow_reset=True)
    app_config = AppConfig(collection_name=False, collect_metrics=False)
    return App(config=app_config, db_config=chroma_config)


def test_chroma_db_init_with_host_and_port(chroma_db):
    settings = chroma_db.client.get_settings()
    assert settings.chroma_server_host == "test-host"
    assert settings.chroma_server_http_port == "1234"


def test_chroma_db_init_with_basic_auth(chroma_db):
    chroma_config = {
        "host": "test-host",
        "port": "1234",
        "chroma_settings": {
            "chroma_client_auth_provider": "chromadb.auth.basic.BasicAuthClientProvider",
            "chroma_client_auth_credentials": "admin:admin",
        },
    }

    db = ChromaDB(config=ChromaDbConfig(**chroma_config))
    settings = db.client.get_settings()
    assert settings.chroma_server_host == "test-host"
    assert settings.chroma_server_http_port == "1234"
    assert settings.chroma_client_auth_provider == chroma_config["chroma_settings"]["chroma_client_auth_provider"]
    assert settings.chroma_client_auth_credentials == chroma_config["chroma_settings"]["chroma_client_auth_credentials"]


@patch("embedchain.vectordb.chroma.chromadb.Client")
def test_app_init_with_host_and_port(mock_client):
    host = "test-host"
    port = "1234"
    config = AppConfig(collect_metrics=False)
    db_config = ChromaDbConfig(host=host, port=port)
    _app = App(config, db_config=db_config)

    called_settings: Settings = mock_client.call_args[0][0]
    assert called_settings.chroma_server_host == host
    assert called_settings.chroma_server_http_port == port


@patch("embedchain.vectordb.chroma.chromadb.Client")
def test_app_init_with_host_and_port_none(mock_client):
    _app = App(config=AppConfig(collect_metrics=False))

    called_settings: Settings = mock_client.call_args[0][0]
    assert called_settings.chroma_server_host is None
    assert called_settings.chroma_server_http_port is None


def test_chroma_db_duplicates_throw_warning(app_with_settings, caplog):
    # Start with a clean app
    app_with_settings.db.reset()

    app = App(config=AppConfig(collect_metrics=False))
    app.db.collection.add(embeddings=[[0, 0, 0]], ids=["0"])
    app.db.collection.add(embeddings=[[0, 0, 0]], ids=["0"])
    assert "Insert of existing embedding ID: 0" in caplog.text
    assert "Add of existing embedding ID: 0" in caplog.text
    app.db.reset()


def test_chroma_db_duplicates_collections_no_warning(app_with_settings, caplog):
    # Start with a clean app
    app_with_settings.db.reset()

    app = App(config=AppConfig(collect_metrics=False))
    app.set_collection_name("test_collection_1")
    app.db.collection.add(embeddings=[[0, 0, 0]], ids=["0"])
    app.set_collection_name("test_collection_2")
    app.db.collection.add(embeddings=[[0, 0, 0]], ids=["0"])
    assert "Insert of existing embedding ID: 0" not in caplog.text
    assert "Add of existing embedding ID: 0" not in caplog.text
    app.db.reset()
    app.set_collection_name("test_collection_1")
    app.db.reset()


def test_chroma_db_collection_init_with_default_collection(app_with_settings):
    app = App(config=AppConfig(collect_metrics=False))
    assert app.db.collection.name == "embedchain_store"


def test_chroma_db_collection_init_with_custom_collection(app_with_settings):
    app = App(config=AppConfig(collect_metrics=False))
    app.set_collection_name(name="test_collection")
    assert app.db.collection.name == "test_collection"


def test_chroma_db_collection_set_collection_name(app_with_settings):
    app = App(config=AppConfig(collect_metrics=False))
    app.set_collection_name("test_collection")
    assert app.db.collection.name == "test_collection"


def test_chroma_db_collection_changes_encapsulated(app_with_settings):
    # Start with a clean app
    app_with_settings.db.reset()

    app = App(config=AppConfig(collect_metrics=False))
    app.set_collection_name("test_collection_1")
    assert app.db.count() == 0

    app.db.collection.add(embeddings=[0, 0, 0], ids=["0"])
    assert app.db.count() == 1

    app.set_collection_name("test_collection_2")
    assert app.db.count() == 0

    app.db.collection.add(embeddings=[0, 0, 0], ids=["0"])
    app.set_collection_name("test_collection_1")
    assert app.db.count() == 1


def test_chroma_db_collection_add_with_skip_embedding(app_with_settings):
    # Start with a clean app
    app_with_settings.db.reset()

    assert app_with_settings.db.count() == 0

    app_with_settings.db.add(
        embeddings=[[0, 0, 0]],
        documents=["document"],
        metadatas=[{"value": "somevalue"}],
        ids=["id"],
        skip_embedding=True,
    )

    assert app_with_settings.db.count() == 1

    data = app_with_settings.db.get(["id"], limit=1)
    expected_value = {
        "documents": ["document"],
        "embeddings": None,
        "ids": ["id"],
        "metadatas": [{"value": "somevalue"}],
    }

    assert data == expected_value

    data = app_with_settings.db.query(input_query=[0, 0, 0], where={}, n_results=1, skip_embedding=True)
    expected_value = ["document"]

    assert data == expected_value


def test_chroma_db_collection_add_with_invalid_inputs(app_with_settings):
    # Start with a clean app
    app_with_settings.db.reset()

    assert app_with_settings.db.count() == 0

    with pytest.raises(ValueError):
        app_with_settings.db.add(
            embeddings=[[0, 0, 0]],
            documents=["document", "document2"],
            metadatas=[{"value": "somevalue"}],
            ids=["id"],
            skip_embedding=True,
        )

    assert app_with_settings.db.count() == 0

    with pytest.raises(ValueError):
        app_with_settings.db.add(
            embeddings=None,
            documents=["document", "document2"],
            metadatas=[{"value": "somevalue"}],
            ids=["id"],
            skip_embedding=True,
        )

    assert app_with_settings.db.count() == 0


def test_chroma_db_collection_collections_are_persistent(app_with_settings):
    # Start with a clean app
    app_with_settings.db.reset()

    app = App(config=AppConfig(collect_metrics=False))
    app.set_collection_name("test_collection_1")
    app.db.collection.add(embeddings=[[0, 0, 0]], ids=["0"])
    del app

    app = App(config=AppConfig(collect_metrics=False))
    app.set_collection_name("test_collection_1")
    assert app.db.count() == 1

    app.db.reset()


def test_chroma_db_collection_parallel_collections(app_with_settings):
    # Start clean
    app_with_settings.db.reset()

    app1 = App(AppConfig(collection_name="test_collection_1", collect_metrics=False))
    app2 = App(AppConfig(collection_name="test_collection_2", collect_metrics=False))

    # cleanup if any previous tests failed or were interrupted
    app1.db.reset()
    app2.db.reset()

    app1.db.collection.add(embeddings=[0, 0, 0], ids=["0"])
    assert app1.db.count() == 1
    assert app2.db.count() == 0

    app1.db.collection.add(embeddings=[[0, 0, 0], [1, 1, 1]], ids=["1", "2"])
    app2.db.collection.add(embeddings=[0, 0, 0], ids=["0"])

    app1.set_collection_name("test_collection_2")
    assert app1.db.count() == 1
    app2.set_collection_name("test_collection_1")
    assert app2.db.count() == 3

    # cleanup
    app1.db.reset()
    app2.db.reset()


def test_chroma_db_collection_ids_share_collections(app_with_settings):
    # Start clean
    app_with_settings.db.reset()

    app1 = App(AppConfig(id="new_app_id_1", collect_metrics=False))
    app1.set_collection_name("one_collection")
    app2 = App(AppConfig(id="new_app_id_2", collect_metrics=False))
    app2.set_collection_name("one_collection")

    app1.db.collection.add(embeddings=[[0, 0, 0], [1, 1, 1]], ids=["0", "1"])
    app2.db.collection.add(embeddings=[0, 0, 0], ids=["2"])

    assert app1.db.count() == 3
    assert app2.db.count() == 3

    # cleanup
    app1.db.reset()
    app2.db.reset()


def test_chroma_db_collection_reset(app_with_settings):
    # Resetting should hit all collections and ids.
    app_with_settings.db.reset()

    app1 = App(AppConfig(id="new_app_id_1", collect_metrics=False), db_config=app_with_settings.db.config)
    app1.set_collection_name("one_collection")
    app2 = App(AppConfig(id="new_app_id_2", collect_metrics=False))
    app2.set_collection_name("one_collection")
    app3 = App(AppConfig(id="new_app_id_1", collect_metrics=False))
    app3.set_collection_name("three_collection")
    app4 = App(AppConfig(id="new_app_id_4", collect_metrics=False))
    app4.set_collection_name("four_collection")

    app1.db.collection.add(embeddings=[0, 0, 0], ids=["1"])
    app2.db.collection.add(embeddings=[0, 0, 0], ids=["2"])
    app3.db.collection.add(embeddings=[0, 0, 0], ids=["3"])
    app4.db.collection.add(embeddings=[0, 0, 0], ids=["4"])

    app1.db.reset()

    assert app1.db.count() == 0
    assert app2.db.count() != 0
    assert app3.db.count() != 0
    assert app4.db.count() != 0
