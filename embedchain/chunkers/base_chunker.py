import hashlib
import logging
from typing import Optional

from embedchain.config.add_config import ChunkerConfig
from embedchain.helpers.json_serializable import JSONSerializable
from embedchain.models.data_type import DataType

logger = logging.getLogger(__name__)


class BaseChunker(JSONSerializable):
    def __init__(self, text_splitter):
        """Initialize the chunker."""
        self.text_splitter = text_splitter
        self.data_type = None

    def create_chunks(self, loader, src, app_id=None, config: Optional[ChunkerConfig] = None):
        """
        Loads data and chunks it.

        :param loader: The loader whose `load_data` method is used to create
        the raw data.
        :param src: The data to be handled by the loader. Can be a URL for
        remote sources or local content for local loaders.
        :param app_id: App id used to generate the doc_id.
        """
        documents = []
        chunk_ids = []
        id_map = {}
        min_chunk_size = config.min_chunk_size if config is not None else 1
        logger.info(f"Skipping chunks smaller than {min_chunk_size} characters")
        data_result = loader.load_data(src)
        data_records = data_result["data"]
        doc_id = data_result["doc_id"]
        # Prefix app_id in the document id if app_id is not None to
        # distinguish between different documents stored in the same
        # elasticsearch or opensearch index
        doc_id = f"{app_id}--{doc_id}" if app_id is not None else doc_id
        metadatas = []
        for data in data_records:
            content = data["content"]

            metadata = data["meta_data"]
            # add data type to meta data to allow query using data type
            metadata["data_type"] = self.data_type.value
            metadata["doc_id"] = doc_id

            # TODO: Currently defaulting to the src as the url. This is done intentianally since some
            # of the data types like 'gmail' loader doesn't have the url in the meta data.
            url = metadata.get("url", src)

            chunks = self.get_chunks(content)
            for chunk in chunks:
                chunk_id = hashlib.sha256((chunk + url).encode()).hexdigest()
                chunk_id = f"{app_id}--{chunk_id}" if app_id is not None else chunk_id
                if id_map.get(chunk_id) is None and len(chunk) >= min_chunk_size:
                    id_map[chunk_id] = True
                    chunk_ids.append(chunk_id)
                    documents.append(chunk)
                    metadatas.append(metadata)
        return {
            "documents": documents,
            "ids": chunk_ids,
            "metadatas": metadatas,
            "doc_id": doc_id,
        }

    def get_chunks(self, content):
        """
        Returns chunks using text splitter instance.

        Override in child class if custom logic.
        """
        return self.text_splitter.split_text(content)

    def set_data_type(self, data_type: DataType):
        """
        set the data type of chunker
        """
        self.data_type = data_type

        # TODO: This should be done during initialization. This means it has to be done in the child classes.

    @staticmethod
    def get_word_count(documents) -> int:
        return sum([len(document.split(" ")) for document in documents])
