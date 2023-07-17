import logging
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


class DocsSiteLoader:
    def __init__(self):
        self.visited_links = set()

    def _get_child_links_recursive(self, url):
        parsed_url = urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        current_path = parsed_url.path

        response = requests.get(url)
        if response.status_code != 200:
            logging.info(f"Failed to fetch the website: {response.status_code}")
            return

        soup = BeautifulSoup(response.text, "html.parser")
        all_links = [link.get("href") for link in soup.find_all("a")]

        child_links = [link for link in all_links if link and link.startswith(current_path) and link != current_path]

        absolute_paths = [urljoin(base_url, link) for link in child_links]

        for link in absolute_paths:
            if link not in self.visited_links:
                self.visited_links.add(link)
                self._get_child_links_recursive(link)

    def _get_all_urls(self, url):
        self.visited_links = set()
        self._get_child_links_recursive(url)
        urls = [link for link in self.visited_links if urlparse(link).netloc == urlparse(url).netloc]
        return urls

    def _load_data_from_url(self, url):
        response = requests.get(url)
        if response.status_code != 200:
            logging.info(f"Failed to fetch the website: {response.status_code}")
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
        return output
