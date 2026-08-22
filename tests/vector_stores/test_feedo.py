from unittest.mock import MagicMock, AsyncMock, patch
import pytest

from mem0.vector_stores.feedo import Feedo
from mem0.configs.vector_stores.feedo import FeedoConfig

import sys
sys.modules["feedo"] = MagicMock()
sys.modules["feedo.router"] = MagicMock()
sys.modules["feedo.modules"] = MagicMock()
sys.modules["feedo.modules.search"] = MagicMock()

@pytest.fixture
def mock_feedo_client():
    client_mock = MagicMock()
    client_mock.index_private_document = AsyncMock()
    client_mock.search = AsyncMock()
    sys.modules["feedo.modules.search"].SearchModule.return_value = client_mock
    yield client_mock

@pytest.fixture
def feedo_store(mock_feedo_client):
    store = Feedo(usage_key="test_key", did="test_did", namespace="test_room")
    return store


def test_insert(feedo_store, mock_feedo_client):
    vectors = [[0.1, 0.2]]
    payloads = [{"data": "Hello feedo"}]
    ids = ["doc_0"]

    feedo_store.insert(vectors=vectors, payloads=payloads, ids=ids)

    # Verify that index_private_document was called
    mock_feedo_client.index_private_document.assert_called_once_with(
        hash_id="doc_0",
        plaintext="Hello feedo",
        metadata={"data": "Hello feedo"},
        namespace="test_room"
    )


def test_search(feedo_store, mock_feedo_client):
    # Mock the return value of client.search
    mock_feedo_client.search.return_value = {
        "documents": [
            {"hash_id": "doc_1", "score": 0.99, "metadata": {"data": "Test memory 1"}},
            {"hash_id": "doc_2", "score": 0.88, "metadata": {"data": "Test memory 2"}}
        ]
    }

    hits = feedo_store.search(query="Test", vectors=[0.1, 0.2], top_k=2)

    assert len(hits) == 2
    assert hits[0].id == "doc_1"
    assert hits[0].score == 0.99
    assert hits[0].payload["data"] == "Test memory 1"

    assert hits[1].id == "doc_2"
    assert hits[1].score == 0.88
    assert hits[1].payload["data"] == "Test memory 2"

    mock_feedo_client.search.assert_called_once_with(
        query="Test",
        limit=2,
        namespace="test_room"
    )
