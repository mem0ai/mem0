from embedchain.chunkers.base_chunker import BaseChunker

from langchain.text_splitter import RecursiveCharacterTextSplitter


TEXT_SPLITTER_CHUNK_PARAMS = {
    "chunk_size": 500,
    "chunk_overlap": 0,
    "length_function": len,
}


class WebPageChunker(BaseChunker):
    def __init__(self):
        text_splitter = RecursiveCharacterTextSplitter(**TEXT_SPLITTER_CHUNK_PARAMS)
        super().__init__(text_splitter)
