import pytest

from embedchain.chunkers.json import JsonChunker
from embedchain.config.add_config import ChunkerConfig


@pytest.fixture
def default_chunker_config():
    return ChunkerConfig(chunk_size=300, chunk_overlap=0, length_function=len)


def test_json_chunker_init(default_chunker_config):
    json_chunker = JsonChunker(config=default_chunker_config)

    assert json_chunker.text_splitter is not None
    assert json_chunker.text_splitter._chunk_size == default_chunker_config.chunk_size
    assert json_chunker.text_splitter._chunk_overlap == default_chunker_config.chunk_overlap
    assert json_chunker.text_splitter._length_function == default_chunker_config.length_function


def test_json_chunker_init_no_config():
    json_chunker = JsonChunker()

    default_chunk_size = 300
    default_chunk_overlap = 0
    default_length_function = len

    assert json_chunker.text_splitter is not None
    assert json_chunker.text_splitter._chunk_size == default_chunk_size
    assert json_chunker.text_splitter._chunk_overlap == default_chunk_overlap
    assert json_chunker.text_splitter._length_function == default_length_function
