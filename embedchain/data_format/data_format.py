from embedchain.loaders.youtube_video import YoutubeVideoLoader
from embedchain.loaders.pdf_file import PdfFileLoader
from embedchain.loaders.web_page import WebPageLoader
from embedchain.loaders.local_qna_pair import LocalQnaPairLoader
from embedchain.loaders.local_text import LocalTextLoader
from embedchain.chunkers.youtube_video import YoutubeVideoChunker
from embedchain.chunkers.pdf_file import PdfFileChunker
from embedchain.chunkers.web_page import WebPageChunker
from embedchain.chunkers.qna_pair import QnaPairChunker
from embedchain.chunkers.text import TextChunker

class DataFormat:
    def __init__(self, data_type):
        self.loader = self._get_loader(data_type)
        self.chunker = self._get_chunker(data_type)
        
    def _get_loader(self, data_type):
        """
        Returns the appropriate data loader for the given data type.

        :param data_type: The type of the data to load.
        :return: The loader for the given data type.
        :raises ValueError: If an unsupported data type is provided.
        """
        loaders = {
            'youtube_video': YoutubeVideoLoader(),
            'pdf_file': PdfFileLoader(),
            'web_page': WebPageLoader(),
            'qna_pair': LocalQnaPairLoader(),
            'text': LocalTextLoader(),
        }
        if data_type in loaders:
            return loaders[data_type]
        else:
            raise ValueError(f"Unsupported data type: {data_type}")

    def _get_chunker(self, data_type):
        """
        Returns the appropriate chunker for the given data type.

        :param data_type: The type of the data to chunk.
        :return: The chunker for the given data type.
        :raises ValueError: If an unsupported data type is provided.
        """
        chunkers = {
            'youtube_video': YoutubeVideoChunker(),
            'pdf_file': PdfFileChunker(),
            'web_page': WebPageChunker(),
            'qna_pair': QnaPairChunker(),
            'text': TextChunker(),
        }
        if data_type in chunkers:
            return chunkers[data_type]
        else:
            raise ValueError(f"Unsupported data type: {data_type}")
