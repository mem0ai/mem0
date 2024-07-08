import pytest

from embedchain.config.vector_db.pinecone import PineconeDBConfig
from embedchain.vectordb.pinecone import PineconeDB


@pytest.fixture
def pinecone_pod_config():
    return PineconeDBConfig(
        index_name="test_collection",
        api_key="test_api_key",
        vector_dimension=3,
        pod_config={"environment": "test_environment", "metadata_config": {"indexed": ["*"]}},
    )


@pytest.fixture
def pinecone_serverless_config():
    return PineconeDBConfig(
        index_name="test_collection",
        api_key="test_api_key",
        vector_dimension=3,
        serverless_config={
            "cloud": "test_cloud",
            "region": "test_region",
        },
    )


def test_pinecone_init_without_config(monkeypatch):
    monkeypatch.setenv("PINECONE_API_KEY", "test_api_key")
    monkeypatch.setattr("embedchain.vectordb.pinecone.PineconeDB._setup_pinecone_index", lambda x: x)
    monkeypatch.setattr("embedchain.vectordb.pinecone.PineconeDB._get_or_create_db", lambda x: x)
    pinecone_db = PineconeDB()

    assert isinstance(pinecone_db, PineconeDB)
    assert isinstance(pinecone_db.config, PineconeDBConfig)
    assert pinecone_db.config.pod_config == {"environment": "gcp-starter", "metadata_config": {"indexed": ["*"]}}
    monkeypatch.delenv("PINECONE_API_KEY")


def test_pinecone_init_with_config(pinecone_pod_config, monkeypatch):
    monkeypatch.setattr("embedchain.vectordb.pinecone.PineconeDB._setup_pinecone_index", lambda x: x)
    monkeypatch.setattr("embedchain.vectordb.pinecone.PineconeDB._get_or_create_db", lambda x: x)
    pinecone_db = PineconeDB(config=pinecone_pod_config)

    assert isinstance(pinecone_db, PineconeDB)
    assert isinstance(pinecone_db.config, PineconeDBConfig)

    assert pinecone_db.config.pod_config == pinecone_pod_config.pod_config

    pinecone_db = PineconeDB(config=pinecone_pod_config)

    assert isinstance(pinecone_db, PineconeDB)
    assert isinstance(pinecone_db.config, PineconeDBConfig)

    assert pinecone_db.config.serverless_config == pinecone_pod_config.serverless_config


class MockListIndexes:
    def names(self):
        return ["test_collection"]


class MockPineconeIndex:
    db = []

    def __init__(*args, **kwargs):
        pass

    def upsert(self, chunk, **kwargs):
        self.db.extend([c for c in chunk])
        return

    def delete(self, *args, **kwargs):
        pass

    def query(self, *args, **kwargs):
        return {
            "matches": [
                {
                    "metadata": {
                        "key": "value",
                        "text": "text_1",
                    },
                    "score": 0.1,
                },
                {
                    "metadata": {
                        "key": "value",
                        "text": "text_2",
                    },
                    "score": 0.2,
                },
            ]
        }

    def fetch(self, *args, **kwargs):
        return {
            "vectors": {
                "key_1": {
                    "metadata": {
                        "source": "1",
                    }
                },
                "key_2": {
                    "metadata": {
                        "source": "2",
                    }
                },
            }
        }

    def describe_index_stats(self, *args, **kwargs):
        return {"total_vector_count": len(self.db)}


class MockPineconeClient:
    def __init__(*args, **kwargs):
        pass

    def list_indexes(self):
        return MockListIndexes()

    def create_index(self, *args, **kwargs):
        pass

    def Index(self, *args, **kwargs):
        return MockPineconeIndex()

    def delete_index(self, *args, **kwargs):
        pass


class MockPinecone:
    def __init__(*args, **kwargs):
        pass

    def Pinecone(*args, **kwargs):
        return MockPineconeClient()

    def PodSpec(*args, **kwargs):
        pass

    def ServerlessSpec(*args, **kwargs):
        pass


class MockEmbedder:
    def embedding_fn(self, documents):
        return [[1, 1, 1] for d in documents]


def test_setup_pinecone_index(pinecone_pod_config, pinecone_serverless_config, monkeypatch):
    monkeypatch.setattr("embedchain.vectordb.pinecone.pinecone", MockPinecone)
    monkeypatch.setenv("PINECONE_API_KEY", "test_api_key")
    pinecone_db = PineconeDB(config=pinecone_pod_config)
    pinecone_db._setup_pinecone_index()

    assert pinecone_db.client is not None
    assert pinecone_db.config.index_name == "test_collection"
    assert pinecone_db.client.list_indexes().names() == ["test_collection"]
    assert pinecone_db.pinecone_index is not None

    pinecone_db = PineconeDB(config=pinecone_serverless_config)
    pinecone_db._setup_pinecone_index()

    assert pinecone_db.client is not None
    assert pinecone_db.config.index_name == "test_collection"
    assert pinecone_db.client.list_indexes().names() == ["test_collection"]
    assert pinecone_db.pinecone_index is not None


def test_get(monkeypatch):
    def mock_pinecone_db():
        monkeypatch.setenv("PINECONE_API_KEY", "test_api_key")
        monkeypatch.setattr("embedchain.vectordb.pinecone.PineconeDB._setup_pinecone_index", lambda x: x)
        monkeypatch.setattr("embedchain.vectordb.pinecone.PineconeDB._get_or_create_db", lambda x: x)
        db = PineconeDB()
        db.pinecone_index = MockPineconeIndex()
        return db

    pinecone_db = mock_pinecone_db()
    ids = pinecone_db.get(["key_1", "key_2"])
    assert ids == {"ids": ["key_1", "key_2"], "metadatas": [{"source": "1"}, {"source": "2"}]}


def test_add(monkeypatch):
    def mock_pinecone_db():
        monkeypatch.setenv("PINECONE_API_KEY", "test_api_key")
        monkeypatch.setattr("embedchain.vectordb.pinecone.PineconeDB._setup_pinecone_index", lambda x: x)
        monkeypatch.setattr("embedchain.vectordb.pinecone.PineconeDB._get_or_create_db", lambda x: x)
        db = PineconeDB()
        db.pinecone_index = MockPineconeIndex()
        db._set_embedder(MockEmbedder())
        return db

    pinecone_db = mock_pinecone_db()
    pinecone_db.add(["text_1", "text_2"], [{"key_1": "value_1"}, {"key_2": "value_2"}], ["key_1", "key_2"])
    assert pinecone_db.count() == 2

    pinecone_db.add(["text_3", "text_4"], [{"key_3": "value_3"}, {"key_4": "value_4"}], ["key_3", "key_4"])
    assert pinecone_db.count() == 4


def test_query(monkeypatch):
    def mock_pinecone_db():
        monkeypatch.setenv("PINECONE_API_KEY", "test_api_key")
        monkeypatch.setattr("embedchain.vectordb.pinecone.PineconeDB._setup_pinecone_index", lambda x: x)
        monkeypatch.setattr("embedchain.vectordb.pinecone.PineconeDB._get_or_create_db", lambda x: x)
        db = PineconeDB()
        db.pinecone_index = MockPineconeIndex()
        db._set_embedder(MockEmbedder())
        return db

    pinecone_db = mock_pinecone_db()
    # without citations
    results = pinecone_db.query(["text_1", "text_2"], n_results=2, where={})
    assert results == ["text_1", "text_2"]
    # with citations
    results = pinecone_db.query(["text_1", "text_2"], n_results=2, where={}, citations=True)
    assert results == [
        ("text_1", {"key": "value", "text": "text_1", "score": 0.1}),
        ("text_2", {"key": "value", "text": "text_2", "score": 0.2}),
    ]
