import hashlib
import logging
from typing import Any, Optional

import requests

try:
    from bs4 import BeautifulSoup
except ImportError:
    raise ImportError(
        "Webpage requires extra dependencies. Install with `pip install beautifulsoup4==4.12.3`"
    ) from None

from embedchain.helpers.json_serializable import register_deserializable
from embedchain.loaders.base_loader import BaseLoader
from embedchain.utils.misc import clean_string

logger = logging.getLogger(__name__)


@register_deserializable
class WebPageLoader(BaseLoader):
    # Shared session for all instances
    _session = requests.Session()

    def load_data(self, url, **kwargs: Optional[dict[str, Any]]):
        """Load data from a web page using a shared requests' session."""
        all_references = False
        for key, value in kwargs.items():
            if key == "all_references":
                all_references = kwargs["all_references"]
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36",  # noqa:E501
        }
        response = self._session.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.content
        reference_links = self.fetch_reference_links(response)
        if all_references:
            for i in reference_links:
                try:
                    response = self._session.get(i, headers=headers, timeout=30)
                    response.raise_for_status()
                    data += response.content
                except Exception as e:
                    logging.error(f"Failed to add URL {url}: {e}")
                    continue

        content = self._get_clean_content(data, url)

        metadata = {"url": url}

        doc_id = hashlib.sha256((content + url).encode()).hexdigest()
        return {
            "doc_id": doc_id,
            "data": [
                {
                    "content": content,
                    "meta_data": metadata,
                }
            ],
        }

    @staticmethod
    def _get_clean_content(html, url) -> str:
        soup = BeautifulSoup(html, "html.parser")
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
        for id_ in ids_to_exclude:
            tags = soup.find_all(id=id_)
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
                f"[{url}] Cleaned page size: {cleaned_size} characters, down from {original_size} (shrunk: {original_size-cleaned_size} chars, {round((1-(cleaned_size/original_size)) * 100, 2)}%)"  # noqa:E501
            )

        return content

    @classmethod
    def close_session(cls):
        cls._session.close()

    def fetch_reference_links(self, response):
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, "html.parser")
            a_tags = soup.find_all("a", href=True)
            reference_links = [a["href"] for a in a_tags if a["href"].startswith("http")]
            return reference_links
        else:
            print(f"Failed to retrieve the page. Status code: {response.status_code}")
            return []
