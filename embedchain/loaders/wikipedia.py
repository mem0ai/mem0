import logging
import wikipedia
import requests

from embedchain.loaders.base_loader import BaseLoader

WIKI_API = "https://en.wikipedia.org/w/api.php?action=query&format=json&titles="

class WikipediaLoader(BaseLoader):
    def load_data(self, url):
        """Load data from a wikipedia."""
        
        # extract page_id for the given wikipedia page
        page_title = url.split("/")[-1]
        response = requests.get(WIKI_API + page_title)
        if response.status_code != 200:
            raise ValueError("Wiki API failed")
        response = response.json()
        pages = response.get("query", {}).get("pages", [-1])
        page_id = int(list(pages)[0])
        
        # extract page content
        if page_id > -1:
            page = wikipedia.page(pageid=page_id)
            if page is None:
                raise ValueError(f"No Wikipedia page found for title: {page_title}")
            logging.info(f"Loading Wikipedia page: {page.title} with page_id: {page_id}")
        else:
            raise ValueError(f"No Wikipedia page found for title: {page_title}")

        meta_data = {
            "url": page.url,
            "title": page.title
        }
        return [{
            "content": page.content,
            "meta_data": meta_data,
        }]
