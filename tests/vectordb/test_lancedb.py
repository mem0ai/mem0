import os
import shutil

import pytest

from embedchain import App
from embedchain.config import AppConfig, LanceDBConfig
from embedchain.vectordb.lancedb import LanceDB

os.environ["OPENAI_API_KEY"] = "test-api-key"


@pytest.fixture
def lancedb():
    return LanceDB(config=LanceDBConfig(dir="test-db", collection_name="test-coll"))


@pytest.fixture
def app_with_settings():
    lancedb_config = LanceDBConfig(allow_reset=True, dir="test-db-reset")
    lancedb = LanceDB(config=lancedb_config)
    app_config = AppConfig(collect_metrics=False)
    return App(config=app_config, db=lancedb)


@pytest.fixture(scope="session", autouse=True)
def cleanup_db():
    yield
    try:
        shutil.rmtree("test-db.lance")
    except OSError as e:
        print("Error: %s - %s." % (e.filename, e.strerror))


@pytest.mark.skip(reason="Logging setup needs to be fixed to make this test to work")
def test_lancedb_duplicates_throw_warning(caplog):
    db = LanceDB(config=LanceDBConfig(allow_reset=True, dir="test-db"))
    app = App(config=AppConfig(collect_metrics=False), db=db)
    embedding = generate_embeddings(0, 1536)
    app.db.collection.add(embeddings=[embedding], ids=["0"])
    app.db.collection.add(embeddings=[embedding], ids=["0"])
    assert "Insert of existing embedding ID: 0" in caplog.text
    assert "Add of existing embedding ID: 0" in caplog.text
    app.db.reset()


def test_lancedb_duplicates_collections_no_warning(caplog):
    db = LanceDB(config=LanceDBConfig(allow_reset=True, dir="test-db"))
    app = App(config=AppConfig(collect_metrics=False), db=db)
    embedding = generate_embeddings(0, 1536)
    app.set_collection_name("test_collection_1")
    app.db.add(embeddings=[embedding], ids=["0"], documents=["doc1"], metadatas=["test"], skip_embedding=True)
    app.set_collection_name("test_collection_2")
    app.db.add(embeddings=[embedding], ids=["0"], documents=["doc1"], metadatas=["test"], skip_embedding=True)
    assert "Insert of existing embedding ID: 0" not in caplog.text
    assert "Add of existing embedding ID: 0" not in caplog.text
    app.db.reset()
    app.set_collection_name("test_collection_1")
    app.db.reset()


def test_lancedb_collection_init_with_default_collection():
    db = LanceDB(config=LanceDBConfig(allow_reset=True, dir="test-db"))
    app = App(config=AppConfig(collect_metrics=False), db=db)
    assert app.db.collection.name == "embedchain_store"


def test_lancedb_collection_init_with_custom_collection():
    db = LanceDB(config=LanceDBConfig(allow_reset=True, dir="test-db"))
    app = App(config=AppConfig(collect_metrics=False), db=db)
    app.set_collection_name(name="test_collection")
    assert app.db.collection.name == "test_collection"


def test_lancedb_collection_set_collection_name():
    db = LanceDB(config=LanceDBConfig(allow_reset=True, dir="test-db"))
    app = App(config=AppConfig(collect_metrics=False), db=db)
    app.set_collection_name("test_collection")
    assert app.db.collection.name == "test_collection"


def test_lancedb_collection_changes_encapsulated():
    db = LanceDB(config=LanceDBConfig(allow_reset=True, dir="test-db"))
    app = App(config=AppConfig(collect_metrics=False), db=db)
    app.set_collection_name("test_collection_1")
    assert app.db.count() == 0
    embedding = generate_embeddings(0, 1536)
    app.db.add(embeddings=[embedding], ids=["0"], documents=["doc1"], metadatas=["test"], skip_embedding=True)
    assert app.db.count() == 1

    app.set_collection_name("test_collection_2")
    assert app.db.count() == 0

    app.db.add(embeddings=[embedding], ids=["0"], documents=["doc1"], metadatas=["test"], skip_embedding=True)
    app.set_collection_name("test_collection_1")
    assert app.db.count() == 1
    app.db.reset()
    app.set_collection_name("test_collection_2")
    app.db.reset()


def test_lancedb_collection_collections_are_persistent():
    db = LanceDB(config=LanceDBConfig(allow_reset=True, dir="test-db"))
    app = App(config=AppConfig(collect_metrics=False), db=db)
    app.set_collection_name("test_collection_1")
    embedding = generate_embeddings(0, 1536)
    app.db.add(embeddings=[embedding], ids=["0"], documents=["doc1"], metadatas=["test"], skip_embedding=True)
    del app

    db = LanceDB(config=LanceDBConfig(allow_reset=True, dir="test-db"))
    app = App(config=AppConfig(collect_metrics=False), db=db)
    app.set_collection_name("test_collection_1")
    assert app.db.count() == 1

    app.db.reset()


def test_lancedb_collection_parallel_collections():
    db1 = LanceDB(config=LanceDBConfig(allow_reset=True, dir="test-db", collection_name="test_collection_1"))
    app1 = App(
        config=AppConfig(collect_metrics=False),
        db=db1,
    )
    db2 = LanceDB(config=LanceDBConfig(allow_reset=True, dir="test-db", collection_name="test_collection_2"))
    app2 = App(
        config=AppConfig(collect_metrics=False),
        db=db2,
    )

    # cleanup if any previous tests failed or were interrupted
    app1.db.reset()
    app2.db.reset()

    embedding = generate_embeddings(0, 1536)
    embedding1 = generate_embeddings(1, 1536)
    app1.db.add(embeddings=[embedding], ids=["0"], documents=["doc1"], metadatas=["test"], skip_embedding=True)

    assert app1.db.count() == 1
    assert app2.db.count() == 0

    app1.db.add(
        embeddings=[embedding, embedding1],
        ids=["1", "2"],
        documents=["doc1", "doc2"],
        metadatas=["test", "test"],
        skip_embedding=True,
    )
    app2.db.add(embeddings=[embedding], ids=["0"], documents=["doc1"], metadatas=["test"], skip_embedding=True)

    app1.set_collection_name("test_collection_2")
    assert app1.db.count() == 1
    app2.set_collection_name("test_collection_1")
    assert app2.db.count() == 3

    # cleanup
    app1.db.reset()
    app2.db.reset()


def test_lancedb_collection_ids_share_collections():
    db1 = LanceDB(config=LanceDBConfig(allow_reset=True, dir="test-db"))
    app1 = App(config=AppConfig(collect_metrics=False), db=db1)
    app1.set_collection_name("one_collection")
    db2 = LanceDB(config=LanceDBConfig(allow_reset=True, dir="test-db"))
    app2 = App(config=AppConfig(collect_metrics=False), db=db2)
    app2.set_collection_name("one_collection")

    # cleanup
    app1.db.reset()
    app2.db.reset()

    embedding = generate_embeddings(0, 1536)
    embedding1 = generate_embeddings(1, 1536)
    embedding2 = generate_embeddings(2, 1536)
    app1.db.add(
        embeddings=[embedding, embedding1],
        ids=["0", "1"],
        documents=["doc1", "doc2"],
        metadatas=["test", "test"],
        skip_embedding=True,
    )
    app2.db.add(embeddings=[embedding2], ids=["2"], documents=["doc3"], metadatas=["test"], skip_embedding=True)

    assert app1.db.count() == 2
    assert app2.db.count() == 3

    # cleanup
    app1.db.reset()
    app2.db.reset()


def test_lancedb_collection_reset():
    db1 = LanceDB(config=LanceDBConfig(allow_reset=True, dir="test-db"))
    app1 = App(config=AppConfig(collect_metrics=False), db=db1)
    app1.set_collection_name("one_collection")
    db2 = LanceDB(config=LanceDBConfig(allow_reset=True, dir="test-db"))
    app2 = App(config=AppConfig(collect_metrics=False), db=db2)
    app2.set_collection_name("two_collection")
    db3 = LanceDB(config=LanceDBConfig(allow_reset=True, dir="test-db"))
    app3 = App(config=AppConfig(collect_metrics=False), db=db3)
    app3.set_collection_name("three_collection")
    db4 = LanceDB(config=LanceDBConfig(allow_reset=True, dir="test-db"))
    app4 = App(config=AppConfig(collect_metrics=False), db=db4)
    app4.set_collection_name("four_collection")

    # cleanup if any previous tests failed or were interrupted
    app1.db.reset()
    app2.db.reset()
    app3.db.reset()
    app4.db.reset()

    embedding = generate_embeddings(0, 1536)
    app1.db.add(embeddings=[embedding], ids=["1"], documents=["doc1"], metadatas=["test"], skip_embedding=True)
    app2.db.add(embeddings=[embedding], ids=["2"], documents=["doc2"], metadatas=["test"], skip_embedding=True)
    app3.db.add(embeddings=[embedding], ids=["3"], documents=["doc3"], metadatas=["test"], skip_embedding=True)
    app4.db.add(embeddings=[embedding], ids=["4"], documents=["doc4"], metadatas=["test"], skip_embedding=True)

    app1.db.reset()

    assert app1.db.count() == 0
    assert app2.db.count() == 1
    assert app3.db.count() == 1
    assert app4.db.count() == 1

    # cleanup
    app2.db.reset()
    app3.db.reset()
    app4.db.reset()


def generate_embeddings(dummy_embed, embed_size):
    generated_embedding = []
    for i in range(embed_size):
        generated_embedding.append(dummy_embed)

    return generated_embedding


def test_lancedb_get_from_collection():
    db = LanceDB(config=LanceDBConfig(allow_reset=True, dir="test-db"))
    app = App(config=AppConfig(collect_metrics=False), db=db)
    app.set_collection_name("test_get_collection_1")
    app.db.reset()
    assert app.db.count() == 0

    embedding = generate_embeddings(0, 1536)
    embedding1 = generate_embeddings(1, 1536)
    embedding2 = generate_embeddings(1536, 1536)
    app.db.add(
        embeddings=[embedding, embedding, embedding1, embedding2],
        ids=["0", "1", "2", "3"],
        documents=["doc1", "doc2", "doc3", "doc4"],
        metadatas=["test", "test", "test", "test"],
        skip_embedding=True,
    )
    fetch_id = ["0"]

    result = app.db.get(fetch_id)
    print(result)
    assert result["ids"] == ["0", "1", "2"]