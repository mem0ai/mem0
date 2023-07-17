import logging

import requests
from bs4 import BeautifulSoup
from bs4.builder import ParserRejectedMarkup

from embedchain.loaders.web_page import WebPageLoader
from embedchain.utils import is_readable


class SitemapLoader:
    def load_data(self, sitemap_url):
        """
        This method takes a sitemap URL as input and retrieves
        all the URLs to use the WebPageLoader to load content
        of each page.
        """
        output = []
        web_page_loader = WebPageLoader()
        response = requests.get(sitemap_url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "xml")

        links = [link.text for link in soup.find_all("loc") if link.parent.name == "url"]
        if len(links) == 0:
            # Get all <loc> tags as a fallback. This might include images.
            links = [link.text for link in soup.find_all("loc")]

        for link in links:
            try:
                each_load_data = web_page_loader.load_data(link)

                if is_readable(each_load_data[0].get("content")):
                    output.append(each_load_data)
                else:
                    logging.warning(f"Page is not readable (too many invalid characters): {link}")
            except ParserRejectedMarkup as e:
                logging.error(f"Failed to parse {link}: {e}")
        return [data[0] for data in output]
