from typing import Optional

from langchain.text_splitter import RecursiveCharacterTextSplitter

from embedchain.chunkers.base_chunker import BaseChunker
from embedchain.config.AddConfig import ChunkerConfig

TEXT_SPLITTER_CHUNK_PARAMS = {
    "chunk_size": 500,
    "chunk_overlap": 0,
    "length_function": len,
}


class WebPageChunker(BaseChunker):
    """Chunker for web page."""

    def __init__(self, config: Optional[ChunkerConfig] = None):
        if config is None:
            config = TEXT_SPLITTER_CHUNK_PARAMS
        text_splitter = RecursiveCharacterTextSplitter(**config)
        super().__init__(text_splitter)
