import os

import pytest

from embedchain import App
from embedchain.config import AppConfig
from embedchain.vectordb.vectara import VectaraDB, VectaraDBConfig

os.environ["OPENAI_API_KEY"] = "test-api-key"


@pytest.fixture
def vectara_db():
    return VectaraDB(config=VectaraDBConfig())


@pytest.fixture
def app_with_settings():
    vectara_config = VectaraDBConfig(allow_reset=True)
    vectara_db = VectaraDB(config=vectara_config)
    app_config = AppConfig(collect_metrics=False)
    return App(config=app_config, db=vectara_db)


def test_vectara_db_duplicates_collections_no_warning(caplog):
    db = VectaraDB(config=VectaraDBConfig(allow_reset=True))
    app = App(config=AppConfig(collect_metrics=False), db=db)
    app.set_collection_name("test_collection_1")
    app.db.collection.add(ids=["0"])
    app.set_collection_name("test_collection_2")
    app.db.collection.add(ids=["0"])
    assert "Insert of existing embedding ID: 0" not in caplog.text
    assert "Add of existing embedding ID: 0" not in caplog.text
    app.db.reset()
    app.set_collection_name("test_collection_1")
    app.db.reset()


def test_vectara_db_collection_init_with_default_collection():
    db = VectaraDB(config=VectaraDBConfig(allow_reset=True))
    app = App(config=AppConfig(collect_metrics=False), db=db)
    assert app.db.collection.name == "embedchain_store"


def test_vectara_db_collection_init_with_custom_collection():
    db = VectaraDB(config=VectaraDBConfig(allow_reset=True))
    app = App(config=AppConfig(collect_metrics=False), db=db)
    app.set_collection_name(name="test_collection")
    assert app.db.collection.name == "test_collection"


def test_vectara_db_collection_set_collection_name():
    db = VectaraDB(config=VectaraDBConfig(allow_reset=True))
    app = App(config=AppConfig(collect_metrics=False), db=db)
    app.set_collection_name("test_collection")
    assert app.db.collection.name == "test_collection"


def test_vectara_db_collection_changes_encapsulated():
    db = VectaraDB(config=VectaraDBConfig(allow_reset=True))
    app = App(config=AppConfig(collect_metrics=False), db=db)
    app.set_collection_name("test_collection_1")
    assert app.db.count() == 0

    app.db.collection.add(ids=["0"])
    assert app.db.count() == 1

    app.set_collection_name("test_collection_2")
    assert app.db.count() == 0

    app.db.collection.add(ids=["0"])
    app.set_collection_name("test_collection_1")
    assert app.db.count() == 1
    app.db.reset()
    app.set_collection_name("test_collection_2")
    app.db.reset()


def test_vectara_db_collection_collections_are_persistent():
    db = VectaraDB(config=VectaraDBConfig(allow_reset=True))
    app = App(config=AppConfig(collect_metrics=False), db=db)
    app.set_collection_name("test_collection_1")
    app.db.collection.add(ids=["0"])
    del app

    db = VectaraDB(config=VectaraDBConfig(allow_reset=True))
    app = App(config=AppConfig(collect_metrics=False), db=db)
    app.set_collection_name("test_collection_1")
    assert app.db.count() == 1

    app.db.reset()


def test_vectara_db_collection_parallel_collections():
    db1 = VectaraDB(config=VectaraDBConfig(allow_reset=True, collection_name="test_collection_1"))
    app1 = App(
        config=AppConfig(collect_metrics=False),
        db=db1,
    )
    db2 = VectaraDB(config=VectaraDBConfig(allow_reset=True, collection_name="test_collection_2"))
    app2 = App(
        config=AppConfig(collect_metrics=False),
        db=db2,
    )

    # cleanup if any previous tests failed or were interrupted
    app1.db.reset()
    app2.db.reset()

    app1.db.collection.add(ids=["0"])
    assert app1.db.count() == 1
    assert app2.db.count() == 0

    app1.db.collection.add(ids=["1", "2"])
    app2.db.collection.add(ids=["0"])

    app1.set_collection_name("test_collection_2")
    assert app1.db.count() == 1
    app2.set_collection_name("test_collection_1")
    assert app2.db.count() == 3

    # cleanup
    app1.db.reset()
    app2.db.reset()


def test_vectara_db_collection_ids_share_collections():
    db1 = VectaraDB(config=VectaraDBConfig(allow_reset=True))
    app1 = App(config=AppConfig(collect_metrics=False), db=db1)
    app1.set_collection_name("one_collection")
    db2 = VectaraDB(config=VectaraDBConfig(allow_reset=True))
    app2 = App(config=AppConfig(collect_metrics=False), db=db2)
    app2.set_collection_name("one_collection")

    app1.db.collection.add(ids=["0", "1"])
    app2.db.collection.add(ids=["2"])

    assert app1.db.count() == 3
    assert app2.db.count() == 3

    # cleanup
    app1.db.reset()
    app2.db.reset()


def test_vectara_db_collection_reset():
    db1 = VectaraDB(config=VectaraDBConfig(allow_reset=True))
    app1 = App(config=AppConfig(collect_metrics=False), db=db1)
    app1.set_collection_name("one_collection")
    db2 = VectaraDB(config=VectaraDBConfig(allow_reset=True))
    app2 = App(config=AppConfig(collect_metrics=False), db=db2)
    app2.set_collection_name("two_collection")
    db3 = VectaraDB(config=VectaraDBConfig(allow_reset=True))
    app3 = App(config=AppConfig(collect_metrics=False), db=db3)
    app3.set_collection_name("three_collection")
    db4 = VectaraDB(config=VectaraDBConfig(allow_reset=True))
    app4 = App(config=AppConfig(collect_metrics=False), db=db4)
    app4.set_collection_name("four_collection")

    app1.db.collection.add(ids=["1"])
    app2.db.collection.add(ids=["2"])
    app3.db.collection.add(ids=["3"])
    app4.db.collection.add(ids=["4"])

    app1.db.reset()

    assert app1.db.count() == 0
    assert app2.db.count() == 1
    assert app3.db.count() == 1
    assert app4.db.count() == 1

    # cleanup
    app2.db.reset()
    app3.db.reset()
    app4.db.reset()
