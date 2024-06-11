import hashlib
import logging

import requests


try:
    from bs4 import BeautifulSoup
except ImportError:
    raise ImportError(
        'Webpage requires extra dependencies. Install with `pip install --upgrade "embedchain[dataloaders]"`'
    ) from None

from embedchain.helpers.json_serializable import register_deserializable
from embedchain.loaders.base_loader import BaseLoader
from embedchain.utils.misc import clean_string

logger = logging.getLogger(__name__)


@register_deserializable
class WebPageLoader(BaseLoader):
    # Shared session for all instances
    _session = requests.Session()

    def load_data(self, url):
        """Load data from a web page using a shared requests' session."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36",  # noqa:E501
        }
        response = self._session.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.content
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
        original_size = len(soup.get_text())

        # Merge exclusion criteria into single pass
        tags_to_exclude = {
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
        }
        ids_to_exclude = {
            "sidebar",
            "main-navigation",
            "menu-main-menu",
        }
        classes_to_exclude = {
            "elementor-location-header",
            "navbar-header",
            "nav",
            "header-sidebar-wrapper",
            "blog-sidebar-wrapper",
            "related-posts",
        }

        # Single pass to decompose unwanted tags, ids, and classes
        for tag in soup.find_all(True):
            if (
                tag.name in tags_to_exclude
                or tag.get("id") in ids_to_exclude
                or any(cls in classes_to_exclude for cls in tag.get("class", []))
            ):
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
