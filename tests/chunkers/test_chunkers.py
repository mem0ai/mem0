import unittest

from embedchain.chunkers.docs_site import DocsSiteChunker
from embedchain.chunkers.docx_file import DocxFileChunker
from embedchain.chunkers.mdx import MdxChunker
from embedchain.chunkers.notion import NotionChunker
from embedchain.chunkers.pdf_file import PdfFileChunker
from embedchain.chunkers.qna_pair import QnaPairChunker
from embedchain.chunkers.sitemap import SitemapChunker
from embedchain.chunkers.table import TableChunker
from embedchain.chunkers.text import TextChunker
from embedchain.chunkers.web_page import WebPageChunker
from embedchain.chunkers.xml import XmlChunker
from embedchain.chunkers.youtube_video import YoutubeVideoChunker
from embedchain.config.add_config import ChunkerConfig


class TestChunkers(unittest.TestCase):
    def setUp(self):
        self.chunker_config = ChunkerConfig(chunk_size=500, chunk_overlap=0, length_function=len)
        self.chunkers = {
            DocsSiteChunker: {"chunk_size": 500, "chunk_overlap": 50, "length_function": len},
            DocxFileChunker: {"chunk_size": 1000, "chunk_overlap": 0, "length_function": len},
            PdfFileChunker: {"chunk_size": 1000, "chunk_overlap": 0, "length_function": len},
            TextChunker: {"chunk_size": 300, "chunk_overlap": 0, "length_function": len},
            MdxChunker: {"chunk_size": 1000, "chunk_overlap": 0, "length_function": len},
            NotionChunker: {"chunk_size": 300, "chunk_overlap": 0, "length_function": len},
            QnaPairChunker: {"chunk_size": 300, "chunk_overlap": 0, "length_function": len},
            TableChunker: {"chunk_size": 300, "chunk_overlap": 0, "length_function": len},
            SitemapChunker: {"chunk_size": 500, "chunk_overlap": 0, "length_function": len},
            WebPageChunker: {"chunk_size": 500, "chunk_overlap": 0, "length_function": len},
            XmlChunker: {"chunk_size": 500, "chunk_overlap": 50, "length_function": len},
            YoutubeVideoChunker: {"chunk_size": 2000, "chunk_overlap": 0, "length_function": len},
        }

    def test_default_config_values(self):
        for chunker_class in self.chunkers:
            chunker = chunker_class()

            self.assertEqual(chunker.text_splitter._chunk_size, self.chunkers[chunker_class]["chunk_size"])
            self.assertEqual(chunker.text_splitter._chunk_overlap, self.chunkers[chunker_class]["chunk_overlap"])
            self.assertEqual(chunker.text_splitter._length_function, self.chunkers[chunker_class]["length_function"])

    def test_custom_config_values(self):
        for chunker_class in self.chunkers:
            chunker = chunker_class(config=self.chunker_config)

            self.assertEqual(chunker.text_splitter._chunk_size, 500)
            self.assertEqual(chunker.text_splitter._chunk_overlap, 0)
            self.assertEqual(chunker.text_splitter._length_function, len)
