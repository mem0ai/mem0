import hashlib

from embedchain.helpers.json_serializable import register_deserializable
from embedchain.loaders.base_loader import BaseLoader
from embedchain.utils import clean_string


@register_deserializable
class UnstructuredLoader(BaseLoader):
    def load_data(self, url):
        """Load data from a Unstructured file."""
        try:
            from langchain.document_loaders import UnstructuredFileLoader
        except ImportError:
            raise ImportError(
                'Unstructured file requires extra dependencies. Install with `pip install --upgrade "embedchain[dataloaders]"`'  # noqa: E501
            ) from None

        loader = UnstructuredFileLoader(url)
        data = []
        all_content = []
        pages = loader.load_and_split()
        if not len(pages):
            raise ValueError("No data found")
        for page in pages:
            content = page.page_content
            content = clean_string(content)
            meta_data = page.metadata
            meta_data["url"] = url
            data.append(
                {
                    "content": content,
                    "meta_data": meta_data,
                }
            )
            all_content.append(content)
        doc_id = hashlib.sha256((" ".join(all_content) + url).encode()).hexdigest()
        return {
            "doc_id": doc_id,
            "data": data,
        }
