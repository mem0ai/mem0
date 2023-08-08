import logging

import requests
from bs4 import BeautifulSoup

from embedchain.loaders.base_loader import BaseLoader
from embedchain.utils import clean_string


class GmailLoader(BaseLoader):
    def load_data(self, query):
        """Load data from gmail."""

        from llama_index import download_loader

        GmailReader = download_loader("GmailReader")
        loader = GmailReader(query=query)
        documents = loader.load_data()

        output = []
        for document in documents:
            with open("out", "w") as f:
                f.write(document.text)
            print(document)

            print(len(documents))

            id_start = document.text.find("Message-ID")
            id_end = document.text.find("\n", id_start)
            id = document.text[id_start + len("Message-ID") : id_end]
            print(id)

            data = document.text
            soup = BeautifulSoup(data, "html.parser")
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
                    f"[{id}] Cleaned page size: {cleaned_size} characters, down from {original_size} (shrunk: {original_size-cleaned_size} chars, {round((1-(cleaned_size/original_size)) * 100, 2)}%)"  # noqa:E501
                )

            output.append({"meta_data": {"url": id}, "content": content})

        print(output)
        return output
