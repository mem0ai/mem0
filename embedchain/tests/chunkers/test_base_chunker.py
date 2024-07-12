import hashlib
from unittest.mock import MagicMock

import pytest

from embedchain.chunkers.base_chunker import BaseChunker
from embedchain.config.add_config import ChunkerConfig
from embedchain.models.data_type import DataType


@pytest.fixture
def text_splitter_mock():
    return MagicMock()


@pytest.fixture
def loader_mock():
    return MagicMock()


@pytest.fixture
def app_id():
    return "test_app"


@pytest.fixture
def data_type():
    return DataType.TEXT


@pytest.fixture
def chunker(text_splitter_mock, data_type):
    text_splitter = text_splitter_mock
    chunker = BaseChunker(text_splitter)
    chunker.set_data_type(data_type)
    return chunker


def test_create_chunks_with_config(chunker, text_splitter_mock, loader_mock, app_id, data_type):
    text_splitter_mock.split_text.return_value = ["Chunk 1", "long chunk"]
    loader_mock.load_data.return_value = {
        "data": [{"content": "Content 1", "meta_data": {"url": "URL 1"}}],
        "doc_id": "DocID",
    }
    config = ChunkerConfig(chunk_size=50, chunk_overlap=0, length_function=len, min_chunk_size=10)
    result = chunker.create_chunks(loader_mock, "test_src", app_id, config)

    assert result["documents"] == ["long chunk"]


def test_create_chunks(chunker, text_splitter_mock, loader_mock, app_id, data_type):
    text_splitter_mock.split_text.return_value = ["Chunk 1", "Chunk 2"]
    loader_mock.load_data.return_value = {
        "data": [{"content": "Content 1", "meta_data": {"url": "URL 1"}}],
        "doc_id": "DocID",
    }

    result = chunker.create_chunks(loader_mock, "test_src", app_id)
    expected_ids = [
        f"{app_id}--" + hashlib.sha256(("Chunk 1" + "URL 1").encode()).hexdigest(),
        f"{app_id}--" + hashlib.sha256(("Chunk 2" + "URL 1").encode()).hexdigest(),
    ]

    assert result["documents"] == ["Chunk 1", "Chunk 2"]
    assert result["ids"] == expected_ids
    assert result["metadatas"] == [
        {
            "url": "URL 1",
            "data_type": data_type.value,
            "doc_id": f"{app_id}--DocID",
        },
        {
            "url": "URL 1",
            "data_type": data_type.value,
            "doc_id": f"{app_id}--DocID",
        },
    ]
    assert result["doc_id"] == f"{app_id}--DocID"


def test_get_chunks(chunker, text_splitter_mock):
    text_splitter_mock.split_text.return_value = ["Chunk 1", "Chunk 2"]

    content = "This is a test content."
    result = chunker.get_chunks(content)

    assert len(result) == 2
    assert result == ["Chunk 1", "Chunk 2"]


def test_set_data_type(chunker):
    chunker.set_data_type(DataType.MDX)
    assert chunker.data_type == DataType.MDX


def test_get_word_count(chunker):
    documents = ["This is a test.", "Another test."]
    result = chunker.get_word_count(documents)
    assert result == 6
