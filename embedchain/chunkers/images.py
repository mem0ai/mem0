import hashlib
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

    def create_chunks(self, loader, src):
        """
        Loads data and chunks it.

        :param loader: The loader which's `load_data` method is used to create
        the raw data.
        :param src: The data to be handled by the loader. Can be a URL for
        remote sources or local content for local loaders.
        """
        documents = []
        embeddings = []
        ids = []
        datas = loader.load_data(src)
        metadatas = []
        for data in datas:
            meta_data = data["meta_data"]
            # add data type to meta data to allow query using data type
            meta_data["data_type"] = self.data_type.value
            chunk_id = hashlib.sha256(meta_data["url"].encode()).hexdigest()
            ids.append(chunk_id)
            documents.append(meta_data["url"])
            embeddings.append(data["content"])
            metadatas.append(meta_data)

        return {
            "documents": documents,
            "embeddings": embeddings,
            "ids": ids,
            "metadatas": metadatas,
        }

    def get_word_count(self, documents):
        return 1