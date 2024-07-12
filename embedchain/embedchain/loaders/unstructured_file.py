import hashlib

from embedchain.helpers.json_serializable import register_deserializable
from embedchain.loaders.base_loader import BaseLoader
from embedchain.utils.misc import clean_string


@register_deserializable
class UnstructuredLoader(BaseLoader):
    def load_data(self, url):
        """Load data from an Unstructured file."""
        try:
            import unstructured  # noqa: F401
            from langchain_community.document_loaders import \
                UnstructuredFileLoader
        except ImportError:
            raise ImportError(
                'Unstructured file requires extra dependencies. Install with `pip install "unstructured[local-inference, all-docs]"`'  # noqa: E501
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
            metadata = page.metadata
            metadata["url"] = url
            data.append(
                {
                    "content": content,
                    "meta_data": metadata,
                }
            )
            all_content.append(content)
        doc_id = hashlib.sha256((" ".join(all_content) + url).encode()).hexdigest()
        return {
            "doc_id": doc_id,
            "data": data,
        }
