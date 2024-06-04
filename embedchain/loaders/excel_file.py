import hashlib
import importlib.util

try:
    from langchain_community.document_loaders import UnstructuredExcelLoader
except ImportError:
    raise ImportError(
        'Excel file requires extra dependencies. Install with `pip install --upgrade "embedchain[dataloaders]"`'
    ) from None

if importlib.util.find_spec("openpyxl") is None and importlib.util.find_spec("xlrd") is None:
    raise ImportError("Excel file requires extra dependencies. Install with `pip install openpyxl xlrd`") from None

from embedchain.helpers.json_serializable import register_deserializable
from embedchain.loaders.base_loader import BaseLoader
from embedchain.utils.misc import clean_string


@register_deserializable
class ExcelFileLoader(BaseLoader):
    def load_data(self, excel_url):
        """Load data from a Excel file."""
        loader = UnstructuredExcelLoader(excel_url)
        pages = loader.load_and_split()

        data = []
        for page in pages:
            content = page.page_content
            content = clean_string(content)

            metadata = page.metadata
            metadata["url"] = excel_url

            data.append({"content": content, "meta_data": metadata})

        doc_id = hashlib.sha256((content + excel_url).encode()).hexdigest()
        return {
            "doc_id": doc_id,
            "data": data,
        }
