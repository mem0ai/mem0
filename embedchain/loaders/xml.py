import hashlib

try:
    from langchain.document_loaders import UnstructuredXMLLoader
except ImportError:
    raise ImportError(
        'XML file requires extra dependencies. Install with `pip install --upgrade "embedchain[dataloaders]"`'
    ) from None
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.loaders.base_loader import BaseLoader
from embedchain.utils import clean_string


@register_deserializable
class XmlLoader(BaseLoader):
    def load_data(self, xml_url):
        """Load data from a XML file."""
        loader = UnstructuredXMLLoader(xml_url)
        data = loader.load()
        content = data[0].page_content
        content = clean_string(content)
        meta_data = data[0].metadata
        meta_data["url"] = meta_data["source"]
        del meta_data["source"]
        output = [{"content": content, "meta_data": meta_data}]
        doc_id = hashlib.sha256((content + xml_url).encode()).hexdigest()
        return {
            "doc_id": doc_id,
            "data": output,
        }
