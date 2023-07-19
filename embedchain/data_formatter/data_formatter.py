from embedchain.chunkers.docs_site import DocsSiteChunker
from embedchain.chunkers.docx_file import DocxFileChunker
from embedchain.chunkers.pdf_file import PdfFileChunker
from embedchain.chunkers.qna_pair import QnaPairChunker
from embedchain.chunkers.text import TextChunker
from embedchain.chunkers.web_page import WebPageChunker
from embedchain.chunkers.youtube_video import YoutubeVideoChunker
from embedchain.config import AddConfig
from embedchain.loaders.docs_site_loader import DocsSiteLoader
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
            "youtube_video": YoutubeVideoLoader(),
            "pdf_file": PdfFileLoader(),
            "web_page": WebPageLoader(),
            "qna_pair": LocalQnaPairLoader(),
            "text": LocalTextLoader(),
            "docx": DocxFileLoader(),
            "sitemap": SitemapLoader(),
            "docs_site": DocsSiteLoader(),
        }
        if data_type in loaders:
            return loaders[data_type]
        else:
            raise ValueError(f"Unsupported data type: {data_type}")

    def _get_chunker(self, data_type, config):
        """
        Returns the appropriate chunker for the given data type.

        :param data_type: The type of the data to chunk.
        :return: The chunker for the given data type.
        :raises ValueError: If an unsupported data type is provided.
        """
        chunker_classes = {
            "youtube_video": YoutubeVideoChunker,
            "pdf_file": PdfFileChunker,
            "web_page": WebPageChunker,
            "qna_pair": QnaPairChunker,
            "text": TextChunker,
            "docx": DocxFileChunker,
            "sitemap": WebPageChunker,
            "docs_site": DocsSiteChunker,
        }
        if data_type in chunker_classes:
            chunker_class = chunker_classes[data_type]
            chunker = chunker_class(config)
            chunker.set_data_type(data_type)
            return chunker
        else:
            raise ValueError(f"Unsupported data type: {data_type}")
