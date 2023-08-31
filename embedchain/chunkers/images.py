from typing import Optional

from langchain.text_splitter import RecursiveCharacterTextSplitter

from embedchain.chunkers.base_chunker import BaseChunker
from embedchain.config.AddConfig import ChunkerConfig


class ImagesChunker(BaseChunker):
    """Chunker for an Image."""

    def __init__(self, config: Optional[ChunkerConfig] = None):
        if config is None:
            config = ChunkerConfig(chunk_size=300, chunk_overlap=0, length_function=len)
        image_splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
            length_function=config.length_function,
        )
        super().__init__(image_splitter)
