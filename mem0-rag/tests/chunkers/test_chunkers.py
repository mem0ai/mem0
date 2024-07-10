from embedchain.chunkers.audio import AudioChunker
from embedchain.chunkers.common_chunker import CommonChunker
from embedchain.chunkers.discourse import DiscourseChunker
from embedchain.chunkers.docs_site import DocsSiteChunker
from embedchain.chunkers.docx_file import DocxFileChunker
from embedchain.chunkers.excel_file import ExcelFileChunker
from embedchain.chunkers.gmail import GmailChunker
from embedchain.chunkers.google_drive import GoogleDriveChunker
from embedchain.chunkers.json import JSONChunker
from embedchain.chunkers.mdx import MdxChunker
from embedchain.chunkers.notion import NotionChunker
from embedchain.chunkers.openapi import OpenAPIChunker
from embedchain.chunkers.pdf_file import PdfFileChunker
from embedchain.chunkers.postgres import PostgresChunker
from embedchain.chunkers.qna_pair import QnaPairChunker
from embedchain.chunkers.sitemap import SitemapChunker
from embedchain.chunkers.slack import SlackChunker
from embedchain.chunkers.table import TableChunker
from embedchain.chunkers.text import TextChunker
from embedchain.chunkers.web_page import WebPageChunker
from embedchain.chunkers.xml import XmlChunker
from embedchain.chunkers.youtube_video import YoutubeVideoChunker
from embedchain.config.add_config import ChunkerConfig

chunker_config = ChunkerConfig(chunk_size=500, chunk_overlap=0, length_function=len)

chunker_common_config = {
    DocsSiteChunker: {"chunk_size": 500, "chunk_overlap": 50, "length_function": len},
    DocxFileChunker: {"chunk_size": 1000, "chunk_overlap": 0, "length_function": len},
    PdfFileChunker: {"chunk_size": 1000, "chunk_overlap": 0, "length_function": len},
    TextChunker: {"chunk_size": 300, "chunk_overlap": 0, "length_function": len},
    MdxChunker: {"chunk_size": 1000, "chunk_overlap": 0, "length_function": len},
    NotionChunker: {"chunk_size": 300, "chunk_overlap": 0, "length_function": len},
    QnaPairChunker: {"chunk_size": 300, "chunk_overlap": 0, "length_function": len},
    TableChunker: {"chunk_size": 300, "chunk_overlap": 0, "length_function": len},
    SitemapChunker: {"chunk_size": 500, "chunk_overlap": 0, "length_function": len},
    WebPageChunker: {"chunk_size": 2000, "chunk_overlap": 0, "length_function": len},
    XmlChunker: {"chunk_size": 500, "chunk_overlap": 50, "length_function": len},
    YoutubeVideoChunker: {"chunk_size": 2000, "chunk_overlap": 0, "length_function": len},
    JSONChunker: {"chunk_size": 1000, "chunk_overlap": 0, "length_function": len},
    OpenAPIChunker: {"chunk_size": 1000, "chunk_overlap": 0, "length_function": len},
    GmailChunker: {"chunk_size": 1000, "chunk_overlap": 0, "length_function": len},
    PostgresChunker: {"chunk_size": 1000, "chunk_overlap": 0, "length_function": len},
    SlackChunker: {"chunk_size": 1000, "chunk_overlap": 0, "length_function": len},
    DiscourseChunker: {"chunk_size": 1000, "chunk_overlap": 0, "length_function": len},
    CommonChunker: {"chunk_size": 2000, "chunk_overlap": 0, "length_function": len},
    GoogleDriveChunker: {"chunk_size": 1000, "chunk_overlap": 0, "length_function": len},
    ExcelFileChunker: {"chunk_size": 1000, "chunk_overlap": 0, "length_function": len},
    AudioChunker: {"chunk_size": 1000, "chunk_overlap": 0, "length_function": len},
}


def test_default_config_values():
    for chunker_class, config in chunker_common_config.items():
        chunker = chunker_class()
        assert chunker.text_splitter._chunk_size == config["chunk_size"]
        assert chunker.text_splitter._chunk_overlap == config["chunk_overlap"]
        assert chunker.text_splitter._length_function == config["length_function"]


def test_custom_config_values():
    for chunker_class, _ in chunker_common_config.items():
        chunker = chunker_class(config=chunker_config)
        assert chunker.text_splitter._chunk_size == 500
        assert chunker.text_splitter._chunk_overlap == 0
        assert chunker.text_splitter._length_function == len
