from typing import Optional
from embedchain.chunkers.base_chunker import BaseChunker
from embedchain.config.AddConfig import ChunkerConfig

from langchain.text_splitter import RecursiveCharacterTextSplitter


TEXT_SPLITTER_CHUNK_PARAMS = {
    "chunk_size": 300,
    "chunk_overlap": 0,
    "length_function": len,
}


class TextChunker(BaseChunker):
    def __init__(self, config: Optional[ChunkerConfig] = None):
        if config is None:
            config = TEXT_SPLITTER_CHUNK_PARAMS
        text_splitter = RecursiveCharacterTextSplitter(**config)
        super().__init__(text_splitter)
