import hashlib

try:
    from langchain.document_loaders import YoutubeLoader
except ImportError:
    raise ImportError(
        'YouTube video requires extra dependencies. Install with `pip install --upgrade "embedchain[dataloaders]"`'
    ) from None
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.loaders.base_loader import BaseLoader
from embedchain.utils import clean_string


@register_deserializable
class YoutubeVideoLoader(BaseLoader):
    def load_data(self, url):
        """Load data from a Youtube video."""
        loader = YoutubeLoader.from_youtube_url(url, add_video_info=True)
        doc = loader.load()
        output = []
        if not len(doc):
            raise ValueError(f"No data found for url: {url}")
        content = doc[0].page_content
        content = clean_string(content)
        meta_data = doc[0].metadata
        meta_data["url"] = url

        output.append(
            {
                "content": content,
                "meta_data": meta_data,
            }
        )
        doc_id = hashlib.sha256((content + url).encode()).hexdigest()
        return {
            "doc_id": doc_id,
            "data": output,
        }
