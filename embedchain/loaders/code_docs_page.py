import requests
from bs4 import BeautifulSoup

from embedchain.utils import clean_string


class CodeDocsPageLoader:
    def load_data(self, url):
        """Load data from a web page."""
        response = requests.get(url)
        data = response.content
        soup = BeautifulSoup(data, "html.parser")
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
        content = None
        for selector in selectors:
            element = soup.select_one(selector)
            if element is not None:
                content = element.prettify()
                break
        if not content:
            content = soup.get_text()
        soup = BeautifulSoup(content, "html.parser")
        for tag in soup(
            [
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
        ):
            tag.string = " "
        for div in soup.find_all("div", {"class": "cell_output"}):
            div.decompose()
        for div in soup.find_all("div", {"class": "output_wrapper"}):
            div.decompose()
        for div in soup.find_all("div", {"class": "output"}):
            div.decompose()
        content = clean_string(soup.get_text())
        output = []
        meta_data = {
            "url": url,
        }
        output.append(
            {
                "content": content,
                "meta_data": meta_data,
            }
        )
        return output
