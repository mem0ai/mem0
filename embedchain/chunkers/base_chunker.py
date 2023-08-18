import hashlib

from embedchain.config import ChunkerConfig
from embedchain.models.data_type import DataType


class BaseChunker:
    def __init__(self, text_splitter, config: ChunkerConfig):
        """Initialize the chunker."""
        self.text_splitter = text_splitter
        self.data_type = None
        self.config = config

    def create_chunks(self, loader, src):
        """
        Loads data and chunks it.

        :param loader: The loader which's `load_data` method is used to create
        the raw data.
        :param src: The data to be handled by the loader. Can be a URL for
        remote sources or local content for local loaders.
        """
        documents = []
        ids = []
        idMap = {}
        datas = loader.load_data(src)
        metadatas = []
        for data in datas:
            content = data["content"]

            meta_data = data["meta_data"]
            # add data type to meta data to allow query using data type
            meta_data["data_type"] = self.data_type.value
            url = meta_data["url"]

            chunks = self.get_chunks(content, meta_data)

            for chunk in chunks:
                chunk_id = hashlib.sha256((chunk + url).encode()).hexdigest()
                if idMap.get(chunk_id) is None:
                    idMap[chunk_id] = True
                    ids.append(chunk_id)
                    documents.append(chunk)
                    metadatas.append(meta_data)
        return {
            "documents": documents,
            "ids": ids,
            "metadatas": metadatas,
        }

    def get_chunks(self, content, metadata):
        """
        Returns chunks using text splitter instance.
        Updates dynamic chunker if used.

        Override in child class if custom logic.
        """
        if self.config._use_dynamic_chunker:
            self._set_dynamic_text_splitter(content, metadata)

        if not self.text_splitter:
            raise UnboundLocalError("`text_splitter` instance not found. This is a bug.")

        return self.text_splitter.split_text(content)

    def set_data_type(self, data_type: DataType):
        """
        set the data type of chunker
        """
        self.data_type = data_type

        # TODO: This should be done during initialization. This means it has to be done in the child classes.

    def _set_dynamic_text_splitter(self, content, metadata):
        """
        Dynamic text splitters are reinitialized for every datas list element.
        This allows them to react to metadata.

        Override in child class if custom logic.
        """
        return NotImplementedError("Dynamic Text Splitter is not implemented.")
