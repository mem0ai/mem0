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
    IMAGE = "image"
    UNSTRUCTURED = "unstructured"
    JSON = "json"
    OPENAPI = "openapi"
    GMAIL = "gmail"
    SUBSTACK = "substack"
    YOUTUBE_CHANNEL = "youtube_channel"
    DISCORD = "discord"
    CUSTOM = "custom"
    RSSFEED = "rss_feed"
    BEEHIIV = "beehiiv"
    GOOGLE_DRIVE = "google_drive"
    DIRECTORY = "directory"
    SLACK = "slack"
    DROPBOX = "dropbox"
    TEXT_FILE = "text_file"
    EXCEL_FILE = "excel_file"


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
    IMAGE = IndirectDataType.IMAGE.value
    UNSTRUCTURED = IndirectDataType.UNSTRUCTURED.value
    JSON = IndirectDataType.JSON.value
    OPENAPI = IndirectDataType.OPENAPI.value
    GMAIL = IndirectDataType.GMAIL.value
    SUBSTACK = IndirectDataType.SUBSTACK.value
    YOUTUBE_CHANNEL = IndirectDataType.YOUTUBE_CHANNEL.value
    DISCORD = IndirectDataType.DISCORD.value
    CUSTOM = IndirectDataType.CUSTOM.value
    RSSFEED = IndirectDataType.RSSFEED.value
    BEEHIIV = IndirectDataType.BEEHIIV.value
    GOOGLE_DRIVE = IndirectDataType.GOOGLE_DRIVE.value
    DIRECTORY = IndirectDataType.DIRECTORY.value
    SLACK = IndirectDataType.SLACK.value
    DROPBOX = IndirectDataType.DROPBOX.value
    TEXT_FILE = IndirectDataType.TEXT_FILE.value
    EXCEL_FILE = IndirectDataType.EXCEL_FILE.value
