import datetime
import itertools
import json
import logging
import os
import re
import string
from typing import Any

from schema import Optional, Or, Schema
from tqdm import tqdm

from embedchain.models.data_type import DataType

logger = logging.getLogger(__name__)


def parse_content(content, type):
    implemented = ["html.parser", "lxml", "lxml-xml", "xml", "html5lib"]
    if type not in implemented:
        raise ValueError(f"Parser type {type} not implemented. Please choose one of {implemented}")

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(content, type)
    original_size = len(str(soup.get_text()))

    tags_to_exclude = [
        "nav",
        "aside",
        "form",
        "header",
        "noscript",
        "svg",
        "canvas",
        "footer",
        "script",
        "style",
    ]
    for tag in soup(tags_to_exclude):
        tag.decompose()

    ids_to_exclude = ["sidebar", "main-navigation", "menu-main-menu"]
    for id in ids_to_exclude:
        tags = soup.find_all(id=id)
        for tag in tags:
            tag.decompose()

    classes_to_exclude = [
        "elementor-location-header",
        "navbar-header",
        "nav",
        "header-sidebar-wrapper",
        "blog-sidebar-wrapper",
        "related-posts",
    ]
    for class_name in classes_to_exclude:
        tags = soup.find_all(class_=class_name)
        for tag in tags:
            tag.decompose()

    content = soup.get_text()
    content = clean_string(content)

    cleaned_size = len(content)
    if original_size != 0:
        logger.info(
            f"Cleaned page size: {cleaned_size} characters, down from {original_size} (shrunk: {original_size-cleaned_size} chars, {round((1-(cleaned_size/original_size)) * 100, 2)}%)"  # noqa:E501
        )

    return content


def clean_string(text):
    """
    This function takes in a string and performs a series of text cleaning operations.

    Args:
        text (str): The text to be cleaned. This is expected to be a string.

    Returns:
        cleaned_text (str): The cleaned text after all the cleaning operations
        have been performed.
    """
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
    len_s = len(s)
    if len_s == 0:
        return False
    printable_chars = set(string.printable)
    printable_ratio = sum(c in printable_chars for c in s) / len_s
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

    import requests
    import yaml

    def is_openapi_yaml(yaml_content):
        # currently the following two fields are required in openapi spec yaml config
        return "openapi" in yaml_content and "info" in yaml_content

    def is_google_drive_folder(url):
        # checks if url is a Google Drive folder url against a regex
        regex = r"^drive\.google\.com\/drive\/(?:u\/\d+\/)folders\/([a-zA-Z0-9_-]+)$"
        return re.match(regex, url)

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
        YOUTUBE_ALLOWED_NETLOCKS = {
            "www.youtube.com",
            "m.youtube.com",
            "youtu.be",
            "youtube.com",
            "vid.plus",
            "www.youtube-nocookie.com",
        }

        if url.netloc in YOUTUBE_ALLOWED_NETLOCKS:
            logger.debug(f"Source of `{formatted_source}` detected as `youtube_video`.")
            return DataType.YOUTUBE_VIDEO

        if url.netloc in {"notion.so", "notion.site"}:
            logger.debug(f"Source of `{formatted_source}` detected as `notion`.")
            return DataType.NOTION

        if url.path.endswith(".pdf"):
            logger.debug(f"Source of `{formatted_source}` detected as `pdf_file`.")
            return DataType.PDF_FILE

        if url.path.endswith(".xml"):
            logger.debug(f"Source of `{formatted_source}` detected as `sitemap`.")
            return DataType.SITEMAP

        if url.path.endswith(".csv"):
            logger.debug(f"Source of `{formatted_source}` detected as `csv`.")
            return DataType.CSV

        if url.path.endswith(".mdx") or url.path.endswith(".md"):
            logger.debug(f"Source of `{formatted_source}` detected as `mdx`.")
            return DataType.MDX

        if url.path.endswith(".docx"):
            logger.debug(f"Source of `{formatted_source}` detected as `docx`.")
            return DataType.DOCX

        if url.path.endswith(
            (".mp3", ".mp4", ".mp2", ".aac", ".wav", ".flac", ".pcm", ".m4a", ".ogg", ".opus", ".webm")
        ):
            logger.debug(f"Source of `{formatted_source}` detected as `audio`.")
            return DataType.AUDIO

        if url.path.endswith(".yaml"):
            try:
                response = requests.get(source)
                response.raise_for_status()
                try:
                    yaml_content = yaml.safe_load(response.text)
                except yaml.YAMLError as exc:
                    logger.error(f"Error parsing YAML: {exc}")
                    raise TypeError(f"Not a valid data type. Error loading YAML: {exc}")

                if is_openapi_yaml(yaml_content):
                    logger.debug(f"Source of `{formatted_source}` detected as `openapi`.")
                    return DataType.OPENAPI
                else:
                    logger.error(
                        f"Source of `{formatted_source}` does not contain all the required \
                        fields of OpenAPI yaml. Check 'https://spec.openapis.org/oas/v3.1.0'"
                    )
                    raise TypeError(
                        "Not a valid data type. Check 'https://spec.openapis.org/oas/v3.1.0', \
                        make sure you have all the required fields in YAML config data"
                    )
            except requests.exceptions.RequestException as e:
                logger.error(f"Error fetching URL {formatted_source}: {e}")

        if url.path.endswith(".json"):
            logger.debug(f"Source of `{formatted_source}` detected as `json_file`.")
            return DataType.JSON

        if "docs" in url.netloc or ("docs" in url.path and url.scheme != "file"):
            # `docs_site` detection via path is not accepted for local filesystem URIs,
            # because that would mean all paths that contain `docs` are now doc sites, which is too aggressive.
            logger.debug(f"Source of `{formatted_source}` detected as `docs_site`.")
            return DataType.DOCS_SITE

        if "github.com" in url.netloc:
            logger.debug(f"Source of `{formatted_source}` detected as `github`.")
            return DataType.GITHUB

        if is_google_drive_folder(url.netloc + url.path):
            logger.debug(f"Source of `{formatted_source}` detected as `google drive folder`.")
            return DataType.GOOGLE_DRIVE_FOLDER

        # If none of the above conditions are met, it's a general web page
        logger.debug(f"Source of `{formatted_source}` detected as `web_page`.")
        return DataType.WEB_PAGE

    elif not isinstance(source, str):
        # For datatypes where source is not a string.

        if isinstance(source, tuple) and len(source) == 2 and isinstance(source[0], str) and isinstance(source[1], str):
            logger.debug(f"Source of `{formatted_source}` detected as `qna_pair`.")
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
            logger.debug(f"Source of `{formatted_source}` detected as `docx`.")
            return DataType.DOCX

        if source.endswith(".csv"):
            logger.debug(f"Source of `{formatted_source}` detected as `csv`.")
            return DataType.CSV

        if source.endswith(".xml"):
            logger.debug(f"Source of `{formatted_source}` detected as `xml`.")
            return DataType.XML

        if source.endswith(".mdx") or source.endswith(".md"):
            logger.debug(f"Source of `{formatted_source}` detected as `mdx`.")
            return DataType.MDX

        if source.endswith(".txt"):
            logger.debug(f"Source of `{formatted_source}` detected as `text`.")
            return DataType.TEXT_FILE

        if source.endswith(".pdf"):
            logger.debug(f"Source of `{formatted_source}` detected as `pdf_file`.")
            return DataType.PDF_FILE

        if source.endswith(".yaml"):
            with open(source, "r") as file:
                yaml_content = yaml.safe_load(file)
                if is_openapi_yaml(yaml_content):
                    logger.debug(f"Source of `{formatted_source}` detected as `openapi`.")
                    return DataType.OPENAPI
                else:
                    logger.error(
                        f"Source of `{formatted_source}` does not contain all the required \
                                  fields of OpenAPI yaml. Check 'https://spec.openapis.org/oas/v3.1.0'"
                    )
                    raise ValueError(
                        "Invalid YAML data. Check 'https://spec.openapis.org/oas/v3.1.0', \
                        make sure to add all the required params"
                    )

        if source.endswith(".json"):
            logger.debug(f"Source of `{formatted_source}` detected as `json`.")
            return DataType.JSON

        if os.path.exists(source) and is_readable(open(source).read()):
            logger.debug(f"Source of `{formatted_source}` detected as `text_file`.")
            return DataType.TEXT_FILE

        # If the source is a valid file, that's not detectable as a type, an error is raised.
        # It does not fall back to text.
        raise ValueError(
            "Source points to a valid file, but based on the filename, no `data_type` can be detected. Please be aware, that not all data_types allow conventional file references, some require the use of the `file URI scheme`. Please refer to the embedchain documentation (https://docs.embedchain.ai/advanced/data_types#remote-data-types)."  # noqa: E501
        )

    else:
        # Source is not a URL.

        # TODO: check if source is gmail query

        # check if the source is valid json string
        if is_valid_json_string(source):
            logger.debug(f"Source of `{formatted_source}` detected as `json`.")
            return DataType.JSON

        # Use text as final fallback.
        logger.debug(f"Source of `{formatted_source}` detected as `text`.")
        return DataType.TEXT


# check if the source is valid json string
def is_valid_json_string(source: str):
    try:
        _ = json.loads(source)
        return True
    except json.JSONDecodeError:
        return False


def validate_config(config_data):
    schema = Schema(
        {
            Optional("app"): {
                Optional("config"): {
                    Optional("id"): str,
                    Optional("name"): str,
                    Optional("log_level"): Or("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
                    Optional("collect_metrics"): bool,
                    Optional("collection_name"): str,
                }
            },
            Optional("llm"): {
                Optional("provider"): Or(
                    "openai",
                    "azure_openai",
                    "anthropic",
                    "huggingface",
                    "cohere",
                    "together",
                    "gpt4all",
                    "ollama",
                    "jina",
                    "llama2",
                    "vertexai",
                    "google",
                    "aws_bedrock",
                    "mistralai",
                    "clarifai",
                    "vllm",
                    "groq",
                    "nvidia",
                ),
                Optional("config"): {
                    Optional("model"): str,
                    Optional("model_name"): str,
                    Optional("number_documents"): int,
                    Optional("temperature"): float,
                    Optional("max_tokens"): int,
                    Optional("top_p"): Or(float, int),
                    Optional("stream"): bool,
                    Optional("online"): bool,
                    Optional("token_usage"): bool,
                    Optional("template"): str,
                    Optional("prompt"): str,
                    Optional("system_prompt"): str,
                    Optional("deployment_name"): str,
                    Optional("where"): dict,
                    Optional("query_type"): str,
                    Optional("api_key"): str,
                    Optional("base_url"): str,
                    Optional("endpoint"): str,
                    Optional("model_kwargs"): dict,
                    Optional("local"): bool,
                    Optional("base_url"): str,
                    Optional("default_headers"): dict,
                    Optional("api_version"): Or(str, datetime.date),
                    Optional("http_client_proxies"): Or(str, dict),
                    Optional("http_async_client_proxies"): Or(str, dict),
                },
            },
            Optional("vectordb"): {
                Optional("provider"): Or(
                    "chroma", "elasticsearch", "opensearch", "lancedb", "pinecone", "qdrant", "weaviate", "zilliz"
                ),
                Optional("config"): object,  # TODO: add particular config schema for each provider
            },
            Optional("embedder"): {
                Optional("provider"): Or(
                    "openai",
                    "gpt4all",
                    "huggingface",
                    "vertexai",
                    "azure_openai",
                    "google",
                    "mistralai",
                    "clarifai",
                    "nvidia",
                    "ollama",
                    "cohere",
                    "aws_bedrock",
                ),
                Optional("config"): {
                    Optional("model"): Optional(str),
                    Optional("deployment_name"): Optional(str),
                    Optional("api_key"): str,
                    Optional("api_base"): str,
                    Optional("title"): str,
                    Optional("task_type"): str,
                    Optional("vector_dimension"): int,
                    Optional("base_url"): str,
                    Optional("endpoint"): str,
                    Optional("model_kwargs"): dict,
                    Optional("http_client_proxies"): Or(str, dict),
                    Optional("http_async_client_proxies"): Or(str, dict),
                },
            },
            Optional("embedding_model"): {
                Optional("provider"): Or(
                    "openai",
                    "gpt4all",
                    "huggingface",
                    "vertexai",
                    "azure_openai",
                    "google",
                    "mistralai",
                    "clarifai",
                    "nvidia",
                    "ollama",
                    "aws_bedrock",
                ),
                Optional("config"): {
                    Optional("model"): str,
                    Optional("deployment_name"): str,
                    Optional("api_key"): str,
                    Optional("title"): str,
                    Optional("task_type"): str,
                    Optional("vector_dimension"): int,
                    Optional("base_url"): str,
                },
            },
            Optional("chunker"): {
                Optional("chunk_size"): int,
                Optional("chunk_overlap"): int,
                Optional("length_function"): str,
                Optional("min_chunk_size"): int,
            },
            Optional("cache"): {
                Optional("similarity_evaluation"): {
                    Optional("strategy"): Or("distance", "exact"),
                    Optional("max_distance"): float,
                    Optional("positive"): bool,
                },
                Optional("config"): {
                    Optional("similarity_threshold"): float,
                    Optional("auto_flush"): int,
                },
            },
            Optional("memory"): {
                Optional("top_k"): int,
            },
        }
    )

    return schema.validate(config_data)


def chunks(iterable, batch_size=100, desc="Processing chunks"):
    """A helper function to break an iterable into chunks of size batch_size."""
    it = iter(iterable)
    total_size = len(iterable)

    with tqdm(total=total_size, desc=desc, unit="batch") as pbar:
        chunk = tuple(itertools.islice(it, batch_size))
        while chunk:
            yield chunk
            pbar.update(len(chunk))
            chunk = tuple(itertools.islice(it, batch_size))
