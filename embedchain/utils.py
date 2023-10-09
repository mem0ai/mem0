import logging
import os
import re
import string
from typing import Any

from embedchain.models.data_type import DataType


def clean_string(text):
    """
    This function takes in a string and performs a series of text cleaning operations.

    Args:
        text (str): The text to be cleaned. This is expected to be a string.

    Returns:
        cleaned_text (str): The cleaned text after all the cleaning operations
        have been performed.
    """
    # Replacement of newline characters:
    text = text.replace("\n", " ")

    # Stripping and reducing multiple spaces to single:
    cleaned_text = re.sub(r"\s+", " ", text.strip())

    # Removing backslashes:
    cleaned_text = cleaned_text.replace("\\", "")

    # Replacing hash characters:
    cleaned_text = cleaned_text.replace("#", " ")

    # Eliminating consecutive non-alphanumeric characters:
    # This regex identifies consecutive non-alphanumeric characters (i.e., not
    # a word character [a-zA-Z0-9_] and not a whitespace) in the string
    # and replaces each group of such characters with a single occurrence of
    # that character.
    # For example, "!!! hello !!!" would become "! hello !".
    cleaned_text = re.sub(r"([^\w\s])\1*", r"\1", cleaned_text)

    return cleaned_text


def is_readable(s):
    """
    Heuristic to determine if a string is "readable" (mostly contains printable characters and forms meaningful words)

    :param s: string
    :return: True if the string is more than 95% printable.
    """
    try:
        printable_ratio = sum(c in string.printable for c in s) / len(s)
    except ZeroDivisionError:
        logging.warning("Empty string processed as unreadable")
        printable_ratio = 0
    return printable_ratio > 0.95  # 95% of characters are printable


def use_pysqlite3():
    """
    Swap std-lib sqlite3 with pysqlite3.
    """
    import platform
    import sqlite3

    if platform.system() == "Linux" and sqlite3.sqlite_version_info < (3, 35, 0):
        try:
            # According to the Chroma team, this patch only works on Linux
            import datetime
            import subprocess
            import sys

            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "pysqlite3-binary", "--quiet", "--disable-pip-version-check"]
            )

            __import__("pysqlite3")
            sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")

            # Let the user know what happened.
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
            print(
                f"{current_time} [embedchain] [INFO]",
                "Swapped std-lib sqlite3 with pysqlite3 for ChromaDb compatibility.",
                f"Your original version was {sqlite3.sqlite_version}.",
            )
        except Exception as e:
            # Escape all exceptions
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
            print(
                f"{current_time} [embedchain] [ERROR]",
                "Failed to swap std-lib sqlite3 with pysqlite3 for ChromaDb compatibility.",
                "Error:",
                e,
            )


def format_source(source: str, limit: int = 20) -> str:
    """
    Format a string to only take the first x and last x letters.
    This makes it easier to display a URL, keeping familiarity while ensuring a consistent length.
    If the string is too short, it is not sliced.
    """
    if len(source) > 2 * limit:
        return source[:limit] + "..." + source[-limit:]
    return source


def detect_datatype(source: Any) -> DataType:
    """
    Automatically detect the datatype of the given source.

    :param source: the source to base the detection on
    :return: data_type string
    """
    from urllib.parse import urlparse

    try:
        if not isinstance(source, str):
            raise ValueError("Source is not a string and thus cannot be a URL.")
        url = urlparse(source)
        # Check if both scheme and netloc are present. Local file system URIs are acceptable too.
        if not all([url.scheme, url.netloc]) and url.scheme != "file":
            raise ValueError("Not a valid URL.")
    except ValueError:
        url = False

    formatted_source = format_source(str(source), 30)

    if url:
        from langchain.document_loaders.youtube import \
            ALLOWED_NETLOCK as YOUTUBE_ALLOWED_NETLOCS

        if url.netloc in YOUTUBE_ALLOWED_NETLOCS:
            logging.debug(f"Source of `{formatted_source}` detected as `youtube_video`.")
            return DataType.YOUTUBE_VIDEO

        if url.netloc in {"notion.so", "notion.site"}:
            logging.debug(f"Source of `{formatted_source}` detected as `notion`.")
            return DataType.NOTION

        if url.path.endswith(".pdf"):
            logging.debug(f"Source of `{formatted_source}` detected as `pdf_file`.")
            return DataType.PDF_FILE

        if url.path.endswith(".xml"):
            logging.debug(f"Source of `{formatted_source}` detected as `sitemap`.")
            return DataType.SITEMAP

        if url.path.endswith(".csv"):
            logging.debug(f"Source of `{formatted_source}` detected as `csv`.")
            return DataType.CSV

        if url.path.endswith(".docx"):
            logging.debug(f"Source of `{formatted_source}` detected as `docx`.")
            return DataType.DOCX

        if "docs" in url.netloc or ("docs" in url.path and url.scheme != "file"):
            # `docs_site` detection via path is not accepted for local filesystem URIs,
            # because that would mean all paths that contain `docs` are now doc sites, which is too aggressive.
            logging.debug(f"Source of `{formatted_source}` detected as `docs_site`.")
            return DataType.DOCS_SITE

        # If none of the above conditions are met, it's a general web page
        logging.debug(f"Source of `{formatted_source}` detected as `web_page`.")
        return DataType.WEB_PAGE

    elif not isinstance(source, str):
        # For datatypes where source is not a string.

        if isinstance(source, tuple) and len(source) == 2 and isinstance(source[0], str) and isinstance(source[1], str):
            logging.debug(f"Source of `{formatted_source}` detected as `qna_pair`.")
            return DataType.QNA_PAIR

        # Raise an error if it isn't a string and also not a valid non-string type (one of the previous).
        # We could stringify it, but it is better to raise an error and let the user decide how they want to do that.
        raise TypeError(
            "Source is not a string and a valid non-string type could not be detected. If you want to embed it, please stringify it, for instance by using `str(source)` or `(', ').join(source)`."  # noqa: E501
        )

    elif os.path.isfile(source):
        # For datatypes that support conventional file references.
        # Note: checking for string is not necessary anymore.

        if source.endswith(".docx"):
            logging.debug(f"Source of `{formatted_source}` detected as `docx`.")
            return DataType.DOCX

        if source.endswith(".csv"):
            logging.debug(f"Source of `{formatted_source}` detected as `csv`.")
            return DataType.CSV

        if source.endswith(".xml"):
            logging.debug(f"Source of `{formatted_source}` detected as `xml`.")
            return DataType.XML

        # If the source is a valid file, that's not detectable as a type, an error is raised.
        # It does not fallback to text.
        raise ValueError(
            "Source points to a valid file, but based on the filename, no `data_type` can be detected. Please be aware, that not all data_types allow conventional file references, some require the use of the `file URI scheme`. Please refer to the embedchain documentation (https://docs.embedchain.ai/advanced/data_types#remote-data-types)."  # noqa: E501
        )

    else:
        # Source is not a URL.

        # Use text as final fallback.
        logging.debug(f"Source of `{formatted_source}` detected as `text`.")
        return DataType.TEXT
