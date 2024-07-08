import concurrent.futures
import hashlib
import logging
import os
from urllib.parse import urlparse

import requests
from tqdm import tqdm

try:
    from bs4 import BeautifulSoup
    from bs4.builder import ParserRejectedMarkup
except ImportError:
    raise ImportError(
        "Sitemap requires extra dependencies. Install with `pip install beautifulsoup4==4.12.3`"
    ) from None

from embedchain.helpers.json_serializable import register_deserializable
from embedchain.loaders.base_loader import BaseLoader
from embedchain.loaders.web_page import WebPageLoader

logger = logging.getLogger(__name__)


@register_deserializable
class SitemapLoader(BaseLoader):
    """
    This method takes a sitemap URL or local file path as input and retrieves
    all the URLs to use the WebPageLoader to load content
    of each page.
    """

    def load_data(self, sitemap_source):
        output = []
        web_page_loader = WebPageLoader()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36",  # noqa:E501
        }

        if urlparse(sitemap_source).scheme in ("http", "https"):
            try:
                response = requests.get(sitemap_source, headers=headers)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "xml")
            except requests.RequestException as e:
                logger.error(f"Error fetching sitemap from URL: {e}")
                return
        elif os.path.isfile(sitemap_source):
            with open(sitemap_source, "r") as file:
                soup = BeautifulSoup(file, "xml")
        else:
            raise ValueError("Invalid sitemap source. Please provide a valid URL or local file path.")

        links = [link.text for link in soup.find_all("loc") if link.parent.name == "url"]
        if len(links) == 0:
            links = [link.text for link in soup.find_all("loc")]

        doc_id = hashlib.sha256((" ".join(links) + sitemap_source).encode()).hexdigest()

        def load_web_page(link):
            try:
                loader_data = web_page_loader.load_data(link)
                return loader_data.get("data")
            except ParserRejectedMarkup as e:
                logger.error(f"Failed to parse {link}: {e}")
            return None

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_link = {executor.submit(load_web_page, link): link for link in links}
            for future in tqdm(concurrent.futures.as_completed(future_to_link), total=len(links), desc="Loading pages"):
                link = future_to_link[future]
                try:
                    data = future.result()
                    if data:
                        output.extend(data)
                except Exception as e:
                    logger.error(f"Error loading page {link}: {e}")

        return {"doc_id": doc_id, "data": output}
