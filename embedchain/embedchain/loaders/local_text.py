import hashlib

from embedchain.helpers.json_serializable import register_deserializable
from embedchain.loaders.base_loader import BaseLoader


@register_deserializable
class LocalTextLoader(BaseLoader):
    def load_data(self, content):
        """Load data from a local text file."""
        url = "local"
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
