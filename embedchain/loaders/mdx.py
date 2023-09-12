import hashlib

from langchain.document_loaders import PyPDFLoader

from embedchain.helper.json_serializable import register_deserializable
from embedchain.loaders.base_loader import BaseLoader
from embedchain.utils import clean_string


@register_deserializable
class MdxLoader(BaseLoader):
    def load_data(self, url):
        """Load data from a mdx file."""
        with open(url, 'r', encoding="utf-8") as infile:
            content = infile.read()
        meta_data = {
            "url": url,
        }
        doc_id = hashlib.sha256((content + url).encode()).hexdigest()
        return {
            "doc_id": doc_id,
            "data": [
                {
                    "content": content,
                    "meta_data": meta_data,
                }
            ],
        }
