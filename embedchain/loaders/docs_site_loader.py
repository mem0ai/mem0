import hashlib
import logging
from urllib.parse import urljoin, urlparse

import requests

try:
    from bs4 import BeautifulSoup
except ImportError:
    raise ImportError(
        'DocsSite requires extra dependencies. Install with `pip install --upgrade "embedchain[dataloaders]"`'
    ) from None


from embedchain.helpers.json_serializable import register_deserializable
from embedchain.loaders.base_loader import BaseLoader

logger = logging.getLogger(__name__)


@register_deserializable
class DocsSiteLoader(BaseLoader):
    def __init__(self):
        self.visited_links = set()

    def _get_child_links_recursive(self, url):
        if url in self.visited_links:
            return

        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        current_path = parsed_url.path

        response = requests.get(url)
        if response.status_code != 200:
            logger.info(f"Failed to fetch the website: {response.status_code}")
            return

        soup = BeautifulSoup(response.text, "html.parser")
        all_links = (link.get("href") for link in soup.find_all("a", href=True))

        child_links = (link for link in all_links if link.startswith(current_path) and link != current_path)

        absolute_paths = set(urljoin(base_url, link) for link in child_links)

        self.visited_links.update(absolute_paths)

        [self._get_child_links_recursive(link) for link in absolute_paths if link not in self.visited_links]

    def _get_all_urls(self, url):
        self.visited_links = set()
        self._get_child_links_recursive(url)
        urls = [link for link in self.visited_links if urlparse(link).netloc == urlparse(url).netloc]
        return urls

    @staticmethod
    def _load_data_from_url(url: str) -> list:
        response = requests.get(url)
        if response.status_code != 200:
            logger.info(f"Failed to fetch the website: {response.status_code}")
            return []

        soup = BeautifulSoup(response.content, "html.parser")
        selectors = [
            "article.bd-article",
            'article[role="main"]',
            "div.md-content",
            'div[role="main"]',
            "div.container",
            "div.section",
            "article",
            "main",
        ]

        output = []
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                content = element.prettify()
                break
        else:
            content = soup.get_text()

        soup = BeautifulSoup(content, "html.parser")
        ignored_tags = [
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
        for tag in soup(ignored_tags):
            tag.decompose()

        content = " ".join(soup.stripped_strings)
        output.append(
            {
                "content": content,
                "meta_data": {"url": url},
            }
        )

        return output

    def load_data(self, url):
        all_urls = self._get_all_urls(url)
        output = []
        for u in all_urls:
            output.extend(self._load_data_from_url(u))
        doc_id = hashlib.sha256((" ".join(all_urls) + url).encode()).hexdigest()
        return {
            "doc_id": doc_id,
            "data": output,
        }
