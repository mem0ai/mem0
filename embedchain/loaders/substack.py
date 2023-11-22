import hashlib
import logging
import time

import requests

from embedchain.helpers.json_serializable import register_deserializable
from embedchain.loaders.base_loader import BaseLoader
from embedchain.utils import is_readable


@register_deserializable
class SubstackLoader(BaseLoader):
    """
    This method takes a sitemap URL as input and retrieves
    all the URLs to use the WebPageLoader to load content
    of each page.
    """

    def load_data(self, url: str):
        try:
            from bs4 import BeautifulSoup
            from bs4.builder import ParserRejectedMarkup
        except ImportError:
            raise ImportError(
                'Substack requires extra dependencies. Install with `pip install --upgrade "embedchain[dataloaders]"`'
            ) from None

        output = []
        response = requests.get(url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "xml")
        links = [link.text for link in soup.find_all("loc") if link.parent.name == "url" and "/p/" in link.text]
        if len(links) == 0:
            links = [link.text for link in soup.find_all("loc") if "/p/" in link.text]

        doc_id = hashlib.sha256((" ".join(links) + url).encode()).hexdigest()

        def serialize_response(soup: BeautifulSoup):
            data = {}

            h1_els = soup.find_all("h1")
            if h1_els is not None and len(h1_els) > 0:
                data["title"] = h1_els[1].text

            description_el = soup.find("meta", {"name": "description"})
            if description_el is not None:
                data["description"] = description_el["content"]

            content_el = soup.find("div", {"class": "available-content"})
            if content_el is not None:
                data["content"] = content_el.text

            like_btn = soup.find("div", {"class": "like-button-container"})
            if like_btn is not None:
                no_of_likes_div = like_btn.find("div", {"class": "label"})
                if no_of_likes_div is not None:
                    data["no_of_likes"] = no_of_likes_div.text

            return data

        def load_link(link: str):
            try:
                each_load_data = requests.get(link)
                each_load_data.raise_for_status()

                soup = BeautifulSoup(response.text, "html.parser")
                data = serialize_response(soup)
                data = str(data)
                if is_readable(data):
                    return data
                else:
                    logging.warning(f"Page is not readable (too many invalid characters): {link}")
            except ParserRejectedMarkup as e:
                logging.error(f"Failed to parse {link}: {e}")
            return None

        for link in links:
            data = load_link(link)
            if data:
                output.append({"content": data, "meta_data": {"url": link}})
            # TODO: allow users to configure this
            time.sleep(1.0)  # added to avoid rate limiting

        return {"doc_id": doc_id, "data": output}
