import hashlib

try:
    import unstructured  # noqa: F401
    from langchain_community.document_loaders import UnstructuredXMLLoader
except ImportError:
    raise ImportError(
        'XML file requires extra dependencies. Install with `pip install "unstructured[local-inference, all-docs]"`'
    ) from None
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.loaders.base_loader import BaseLoader
from embedchain.utils.misc import clean_string


@register_deserializable
class XmlLoader(BaseLoader):
    def load_data(self, xml_url):
        """Load data from a XML file."""
        loader = UnstructuredXMLLoader(xml_url)
        data = loader.load()
        content = data[0].page_content
        content = clean_string(content)
        metadata = data[0].metadata
        metadata["url"] = metadata["source"]
        del metadata["source"]
        output = [{"content": content, "meta_data": metadata}]
        doc_id = hashlib.sha256((content + xml_url).encode()).hexdigest()
        return {
            "doc_id": doc_id,
            "data": output,
        }
