from enum import Enum


class DirectDataType(Enum):
    """
    DirectDataType enum contains data types that contain raw data directly.
    """

    TEXT = "text"


class IndirectDataType(Enum):
    """
    IndirectDataType enum contains data types that contain references to data stored elsewhere.
    """

    YOUTUBE_VIDEO = "youtube_video"
    PDF_FILE = "pdf_file"
    WEB_PAGE = "web_page"
    SITEMAP = "sitemap"
    XML = "xml"
    DOCX = "docx"
    DOCS_SITE = "docs_site"
    NOTION = "notion"
    CSV = "csv"
    MDX = "mdx"
    IMAGES = "images"
    UNSTRUCTURED = "unstructured"
    JSON = "json"
    OPENAPI = "openapi"
    GMAIL = "gmail"
    POSTGRES = "postgres"
    MYSQL = "mysql"
    SLACK = "slack"
    DISCOURSE = "discourse"
    SUBSTACK = "substack"
    GITHUB = "github"
    YOUTUBE_CHANNEL = "youtube_channel"


class SpecialDataType(Enum):
    """
    SpecialDataType enum contains data types that are neither direct nor indirect, or simply require special attention.
    """

    QNA_PAIR = "qna_pair"


class DataType(Enum):
    TEXT = DirectDataType.TEXT.value
    YOUTUBE_VIDEO = IndirectDataType.YOUTUBE_VIDEO.value
    PDF_FILE = IndirectDataType.PDF_FILE.value
    WEB_PAGE = IndirectDataType.WEB_PAGE.value
    SITEMAP = IndirectDataType.SITEMAP.value
    XML = IndirectDataType.XML.value
    DOCX = IndirectDataType.DOCX.value
    DOCS_SITE = IndirectDataType.DOCS_SITE.value
    NOTION = IndirectDataType.NOTION.value
    CSV = IndirectDataType.CSV.value
    MDX = IndirectDataType.MDX.value
    QNA_PAIR = SpecialDataType.QNA_PAIR.value
    IMAGES = IndirectDataType.IMAGES.value
    UNSTRUCTURED = IndirectDataType.UNSTRUCTURED.value
    JSON = IndirectDataType.JSON.value
    OPENAPI = IndirectDataType.OPENAPI.value
    GMAIL = IndirectDataType.GMAIL.value
    POSTGRES = IndirectDataType.POSTGRES.value
    MYSQL = IndirectDataType.MYSQL.value
    SLACK = IndirectDataType.SLACK.value
    DISCOURSE = IndirectDataType.DISCOURSE.value
    SUBSTACK = IndirectDataType.SUBSTACK.value
    GITHUB = IndirectDataType.GITHUB.value
    YOUTUBE_CHANNEL = IndirectDataType.YOUTUBE_CHANNEL.value
