import hashlib

from embedchain.helpers.json_serializable import register_deserializable
from embedchain.loaders.base_loader import BaseLoader


@register_deserializable
class MdxLoader(BaseLoader):
    def load_data(self, url):
        """Load data from a mdx file."""
        with open(url, "r", encoding="utf-8") as infile:
            content = infile.read()
        metadata = {
            "url": url,
        }
        doc_id = hashlib.sha256((content + url).encode()).hexdigest()
        return {
            "doc_id": doc_id,
            "data": [
                {
                    "content": content,
                    "meta_data": metadata,
                }
            ],
        }
