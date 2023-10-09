import hashlib
import logging

import requests
from bs4 import BeautifulSoup

from embedchain.helper.json_serializable import register_deserializable
from embedchain.loaders.base_loader import BaseLoader
from embedchain.utils import clean_string


@register_deserializable
class WebPageLoader(BaseLoader):
    def load_data(self, url):
        """Load data from a web page."""
        response = requests.get(url)
        data = response.content
        content = self._get_clean_content(data, url)

        meta_data = {
            "url": url,
        }

        doc_id = hashlib.sha256((content + url).encode()).hexdigest()
        return {
            "doc_id": doc_id,
            "data": [
                {
                    "content": content,
                    "meta_data": meta_data,
                }
            ],
        }

    def _get_clean_content(self, html, url) -> str:
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
            logging.info(
                f"[{url}] Cleaned page size: {cleaned_size} characters, down from {original_size} (shrunk: {original_size-cleaned_size} chars, {round((1-(cleaned_size/original_size)) * 100, 2)}%)"  # noqa:E501
            )

        return content
