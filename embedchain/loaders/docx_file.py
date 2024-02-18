import hashlib

try:
    from langchain_community.document_loaders import Docx2txtLoader
except ImportError:
    raise ImportError(
        'Docx file requires extra dependencies. Install with `pip install --upgrade "embedchain[dataloaders]"`'
    ) from None
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.loaders.base_loader import BaseLoader


@register_deserializable
class DocxFileLoader(BaseLoader):
    def load_data(self, url):
        """Load data from a .docx file."""
        loader = Docx2txtLoader(url)
        output = []
        data = loader.load()
        content = data[0].page_content
        metadata = data[0].metadata
        metadata["url"] = "local"
        output.append({"content": content, "meta_data": metadata})
        doc_id = hashlib.sha256((content + url).encode()).hexdigest()
        return {
            "doc_id": doc_id,
            "data": output,
        }
