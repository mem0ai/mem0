import logging
import re
import string
from typing import Any


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
    printable_ratio = sum(c in string.printable for c in s) / len(s)
    return printable_ratio > 0.95  # 95% of characters are printable


def use_pysqlite3():
    """
    Swap std-lib sqlite3 with pysqlite3.
    """
    import platform

    if platform.system() == "Linux":
        # According to the Chroma team, this patch only works on Linux
        import subprocess
        import sys

        subprocess.check_call([sys.executable, "-m", "pip", "install", "pysqlite3-binary"])

        __import__("pysqlite3")
        sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
        # Don't be surprised if this doesn't log as you expect, because the logger is instantiated after the import
        logging.info("Swapped std-lib sqlite3 with pysqlite3")


def format_source(source: str, limit: int = 20) -> str:
    """
    Format a string to only take the first x and last x letters.
    This makes it easier to display a URL, keeping familiarity while ensuring a consistent length.
    If the string is too short, it is not sliced.
    """
    if len(source) > 2 * limit:
        return source[:limit] + "..." + source[-limit:]
    return source


def detect_datatype(source: Any) -> str:
    """
    Automatically detect the datatype of the given source.

    :param source: the source to base the detection on
    :return: data_type string
    """
    from urllib.parse import urlparse

    try:
        url = urlparse(source)
        # Check if both scheme and netloc are present
        if not all([url.scheme, url.netloc]):
            raise ValueError("Not a valid URL.")
    except ValueError:
        url = False

    formatted_source = format_source(str(source), 30)

    if url:
        if ("youtube" in url.netloc and "watch" in url.path) or ("youtu.be") in url.netloc:
            logging.debug(f"Source of `{formatted_source}` detected as `youtube_video`.")
            return "youtube_video"

        if url.path.endswith(".pdf"):
            logging.debug(f"Source of `{formatted_source}` detected as `pdf_file`.")
            return "pdf_file"

        if url.path.endswith(".xml"):
            logging.debug(f"Source of `{formatted_source}` detected as `sitemap`.")
            return "sitemap"

        if url.path.endswith(".docx"):
            logging.debug(f"Source of `{formatted_source}` detected as `docx`.")
            return "docx"

        if "docs" in url.netloc or "docs" in url.path:
            logging.debug(f"Source of `{formatted_source}` detected as `docs_site`.")
            return "docs_site"

        # If none of the above conditions are met, it's a general web page
        logging.debug(f"Source of `{formatted_source}` detected as `web_page`.")
        return "web_page"

    else:
        # Source is not a URL

        if isinstance(source, tuple) and len(source) == 2:
            logging.debug(f"Source of `{formatted_source}` detected as `qna_pair`.")
            return "qna_pair"

        logging.debug(f"Source of `{formatted_source}` detected as `text`.")
        return "text"
