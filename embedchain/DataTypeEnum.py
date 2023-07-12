from enum import Enum, unique

@unique
class DataType(Enum):
    YOUTUBE_VIDEO = "youtube_video"
    PDF_FILE = "pdf_file"
    WEB_PAGE = "web_page"
    QNA_PAIR = "qna_pair"
    TEXT = "text"
    DOCX = "docx"


    @staticmethod
    def get_enum(enum_str):
        for member in DataType:
            if member.value == enum_str:
                return member
        raise ValueError(f"Invalid enum string: {enum_str}")
