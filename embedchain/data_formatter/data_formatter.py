from embedchain.DataTypeEnum import DataType
from embedchain.chunkers.docx_file import DocxFileChunker
from embedchain.chunkers.pdf_file import PdfFileChunker
from embedchain.chunkers.qna_pair import QnaPairChunker
from embedchain.chunkers.text import TextChunker
from embedchain.chunkers.web_page import WebPageChunker
from embedchain.chunkers.youtube_video import YoutubeVideoChunker
from embedchain.config import AddConfig
from embedchain.loaders.docx_file import DocxFileLoader
from embedchain.loaders.local_qna_pair import LocalQnaPairLoader
from embedchain.loaders.local_text import LocalTextLoader
from embedchain.loaders.pdf_file import PdfFileLoader
from embedchain.loaders.sitemap import SitemapLoader
from embedchain.loaders.web_page import WebPageLoader
from embedchain.loaders.youtube_video import YoutubeVideoLoader


class DataFormatter:
    """
    DataFormatter is an internal utility class which abstracts the mapping for
    loaders and chunkers to the data_type entered by the user in their
    .add or .add_local method call
    """

    def __init__(self, data_type: str, config: AddConfig):
        self.loader = self._get_loader(data_type, config.loader)
        self.chunker = self._get_chunker(data_type, config.chunker)

    def _get_loader(self, data_type, config):
        """
        Returns the appropriate data loader for the given data type.

        :param data_type: The type of the data to load.
        :return: The loader for the given data type.
        :raises ValueError: If an unsupported data type is provided.
        """
        loaders = {
            DataType.YOUTUBE_VIDEO: YoutubeVideoLoader(),
            DataType.PDF_FILE: PdfFileLoader(),
            DataType.WEB_PAGE: WebPageLoader(),
            DataType.QNA_PAIR: LocalQnaPairLoader(),
            DataType.TEXT: LocalTextLoader(),
            DataType.DOCX: DocxFileLoader(),
            "sitemap": SitemapLoader(),
        }
        if isinstance(data_type, DataType):
            return loaders[data_type]
        # compatible string
        if not isinstance(data_type, DataType):
            data_type_enum = DataType.get_enum(data_type)
            return loaders[data_type_enum]
        else:
            raise ValueError(f"Unsupported data type: {data_type}, please use DataType enum")

    def _get_chunker(self, data_type, config):
        """
        Returns the appropriate chunker for the given data type.

        :param data_type: The type of the data to chunk.
        :return: The chunker for the given data type.
        :raises ValueError: If an unsupported data type is provided.
        """
        chunkers = {
            DataType.YOUTUBE_VIDEO: YoutubeVideoChunker(config),
            DataType.PDF_FILE: PdfFileChunker(config),
            DataType.WEB_PAGE: WebPageChunker(config),
            DataType.QNA_PAIR: QnaPairChunker(config),
            DataType.TEXT: TextChunker(config),
            DataType.DOCX: DocxFileChunker(config),
            "sitemap": WebPageChunker(config),
        }
        if isinstance(data_type, DataType):
            return chunkers[data_type]
        # compatible string
        if not isinstance(data_type, DataType):
            data_type_enum = DataType.get_enum(data_type)
            return chunkers[data_type_enum]
        else:
            raise ValueError(f"Unsupported data type: {data_type}, please use DataType enum")
