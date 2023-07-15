import logging

import requests
from bs4 import BeautifulSoup
from bs4.builder import ParserRejectedMarkup

from embedchain.loaders.web_page import WebPageLoader


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
        links = [link.text for link in soup.find_all("loc")]
        for link in links:
            try:
                each_load_data = web_page_loader.load_data(link)
                output.append(each_load_data)
            except ParserRejectedMarkup as e:
                logging.error(f"Failed to parse {link}: {e}")
        return [data[0] for data in output]
