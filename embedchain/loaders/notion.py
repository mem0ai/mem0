import hashlib
import logging
import os

try:
    from llama_hub.notion.base import NotionPageReader
except ImportError:
    raise ImportError(
        "Notion requires extra dependencies. Install with `pip install --upgrade embedchain[community]`"
    ) from None


from embedchain.helper.json_serializable import register_deserializable
from embedchain.loaders.base_loader import BaseLoader
from embedchain.utils import clean_string


@register_deserializable
class NotionLoader(BaseLoader):
    def load_data(self, source):
        """Load data from a PDF file."""

        # Reformat Id to match notion expectation
        id = source[-32:]
        formatted_id = f"{id[:8]}-{id[8:12]}-{id[12:16]}-{id[16:20]}-{id[20:]}"
        logging.debug(f"Extracted notion page id as: {formatted_id}")

        # Get page through the notion api
        integration_token = os.getenv("NOTION_INTEGRATION_TOKEN")
        reader = NotionPageReader(integration_token=integration_token)
        documents = reader.load_data(page_ids=[formatted_id])

        # Extract text
        raw_text = documents[0].text

        # Clean text
        text = clean_string(raw_text)
        doc_id = hashlib.sha256((text + source).encode()).hexdigest()
        return {
            "doc_id": doc_id,
            "data": [
                {
                    "content": text,
                    "meta_data": {"url": f"notion-{formatted_id}"},
                }
            ],
        }
