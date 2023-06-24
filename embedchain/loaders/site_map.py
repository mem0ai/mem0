import requests

from bs4 import BeautifulSoup
from embedchain.loaders.web_page import WebPageLoader

class SitemapLoader:
    def load_data(self, sitemap_url):
        """
            This method takes a sitemap url as input and retrieves
            all the urls to use the WebPageLoader to load content
            of each page.
        """
        output = []
        web_page_loader = WebPageLoader()

        response = requests.get(sitemap_url)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, features="xml")
            links = [link.text for link in soup.find_all('loc')]

            for link in links:
                each_load_data = web_page_loader.load_data(link)
                # WebPageLoader returns a list with single element which is extracted and appended to 
                # the output list containing data for all pages
                output.append(each_load_data[0])

            return output
        
        else:
            raise response.raise_for_status()

