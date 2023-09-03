from embedchain.chunkers.docs_site import DocsSiteChunker
from embedchain.chunkers.docx_file import DocxFileChunker
from embedchain.chunkers.notion import NotionChunker
from embedchain.chunkers.pdf_file import PdfFileChunker
from embedchain.chunkers.qna_pair import QnaPairChunker
from embedchain.chunkers.table import TableChunker
from embedchain.chunkers.text import TextChunker
from embedchain.chunkers.web_page import WebPageChunker
from embedchain.chunkers.youtube_video import YoutubeVideoChunker
from embedchain.config import AddConfig
from embedchain.helper_classes.json_serializable import JSONSerializable
from embedchain.loaders.csv import CsvLoader
from embedchain.loaders.docs_site_loader import DocsSiteLoader
from embedchain.loaders.docx_file import DocxFileLoader
from embedchain.loaders.local_qna_pair import LocalQnaPairLoader
from embedchain.loaders.local_text import LocalTextLoader
from embedchain.loaders.pdf_file import PdfFileLoader
from embedchain.loaders.sitemap import SitemapLoader
from embedchain.loaders.web_page import WebPageLoader
from embedchain.loaders.youtube_video import YoutubeVideoLoader
from embedchain.models.data_type import DataType


class DataFormatter(JSONSerializable):
    """
    DataFormatter is an internal utility class which abstracts the mapping for
    loaders and chunkers to the data_type entered by the user in their
    .add or .add_local method call
    """

    def __init__(self, data_type: DataType, config: AddConfig):
        self.loader = self._get_loader(data_type, config.loader)
        self.chunker = self._get_chunker(data_type, config.chunker)

    def _get_loader(self, data_type: DataType, config):
        """
        Returns the appropriate data loader for the given data type.

        :param data_type: The type of the data to load.
        :return: The loader for the given data type.
        :raises ValueError: If an unsupported data type is provided.
        """
        loaders = {
            DataType.YOUTUBE_VIDEO: YoutubeVideoLoader,
            DataType.PDF_FILE: PdfFileLoader,
            DataType.WEB_PAGE: WebPageLoader,
            DataType.QNA_PAIR: LocalQnaPairLoader,
            DataType.TEXT: LocalTextLoader,
            DataType.DOCX: DocxFileLoader,
            DataType.SITEMAP: SitemapLoader,
            DataType.DOCS_SITE: DocsSiteLoader,
            DataType.CSV: CsvLoader,
        }
        lazy_loaders = {DataType.NOTION}
        if data_type in loaders:
            loader_class = loaders[data_type]
            loader = loader_class()
            return loader
        elif data_type in lazy_loaders:
            if data_type == DataType.NOTION:
                from embedchain.loaders.notion import NotionLoader

                return NotionLoader()
            else:
                raise ValueError(f"Unsupported data type: {data_type}")
        else:
            raise ValueError(f"Unsupported data type: {data_type}")

    def _get_chunker(self, data_type: DataType, config):
        """
        Returns the appropriate chunker for the given data type.

        :param data_type: The type of the data to chunk.
        :return: The chunker for the given data type.
        :raises ValueError: If an unsupported data type is provided.
        """
        chunker_classes = {
            DataType.YOUTUBE_VIDEO: YoutubeVideoChunker,
            DataType.PDF_FILE: PdfFileChunker,
            DataType.WEB_PAGE: WebPageChunker,
            DataType.QNA_PAIR: QnaPairChunker,
            DataType.TEXT: TextChunker,
            DataType.DOCX: DocxFileChunker,
            DataType.WEB_PAGE: WebPageChunker,
            DataType.DOCS_SITE: DocsSiteChunker,
            DataType.NOTION: NotionChunker,
            DataType.CSV: TableChunker,
        }
        if data_type in chunker_classes:
            chunker_class = chunker_classes[data_type]
            chunker = chunker_class(config)
            chunker.set_data_type(data_type)
            return chunker
        else:
            raise ValueError(f"Unsupported data type: {data_type}")
