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
    DOCX = "docx"
    DOCS_SITE = "docs_site"
    NOTION = "notion"
    CSV = "csv"
    MDX = "mdx"


class SpecialDataType(Enum):
    """
    SpeciallDataType enum contains data types that are neither direct or indirect, or simply require special attention.
    """

    QNA_PAIR = "qna_pair"


DataType = Enum(
    "DataType",
    {
        **{item.name: item.value for item in DirectDataType},
        **{item.name: item.value for item in IndirectDataType},
        **{item.name: item.value for item in SpecialDataType},
    },
)
