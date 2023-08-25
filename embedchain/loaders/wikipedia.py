import logging
import wikipedia

from embedchain.loaders.base_loader import BaseLoader


class WikipediaLoader(BaseLoader):
    def load_data(self, title):
        """Load data from a wikipedia."""
        output = []

        try:
            page = wikipedia.page(title)
        except wikipedia.exceptions.DisambiguationError as e:
            logging.error(f"DisambiguationError: {e.options}")
            page = None
        except wikipedia.exceptions.PageError as e:
            logging.error(f"PageError: {e}")
            page = None

        if page is not None:
            meta_data = {
                "url": page.url,
                "title": page.title
            }
            output.append({
                "content": page.content,
                "meta_data": meta_data,
            })

        return output
