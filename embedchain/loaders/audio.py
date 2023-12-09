import hashlib

from embedchain.helpers.json_serializable import register_deserializable
from embedchain.loaders.base_loader import BaseLoader


@register_deserializable
class AudioLoader(BaseLoader):
    def load_data(self, url):
        """Load data from an Audio file."""
        try:
            import whisper
        except ImportError:
            raise ImportError(
                'Audio requires extra dependencies. Install with `pip install --upgrade "embedchain[audio]"`'
            ) from None
        
        model = whisper.load_model("base.en")
        result = model.transcribe(url)
        content = result["text"]
        meta_data = {
            "url": url,
        }
        doc_id = hashlib.sha256((content + url).encode()).hexdigest()
        return {
            "doc_id": doc_id,
            "data": [
                {
                    "content": content,
                    "meta_data": meta_data,
                }
            ],
        }
