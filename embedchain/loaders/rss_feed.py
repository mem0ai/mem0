import hashlib

from embedchain.helpers.json_serializable import register_deserializable
from embedchain.loaders.base_loader import BaseLoader


@register_deserializable
class RSSFeedLoader(BaseLoader):
    """Loader for RSS Feed."""

    def load_data(self, url):
        """Load data from a rss feed."""
        output = self.get_rss_content(url)
        doc_id = hashlib.sha256((str(output) + url).encode()).hexdigest()
        return {
            "doc_id": doc_id,
            "data": output,
        }

    @staticmethod
    def serialize_metadata(metadata):
        for key, value in metadata.items():
            if not isinstance(value, (str, int, float, bool)):
                metadata[key] = str(value)

        return metadata

    @staticmethod
    def get_rss_content(url: str):
        try:
            from langchain_community.document_loaders import \
                RSSFeedLoader as LangchainRSSFeedLoader
        except ImportError:
            raise ImportError(
                """RSSFeedLoader file requires extra dependencies.
                Install with `pip install --upgrade "embedchain[rss_feed]"`"""
            ) from None

        output = []
        loader = LangchainRSSFeedLoader(urls=[url])
        data = loader.load()

        for entry in data:
            metadata = RSSFeedLoader.serialize_metadata(entry.metadata)
            metadata.update({"url": url})
            output.append(
                {
                    "content": entry.page_content,
                    "meta_data": metadata,
                }
            )

        return output
