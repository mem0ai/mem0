import hashlib
import os

import validators

from embedchain.helpers.json_serializable import register_deserializable
from embedchain.loaders.base_loader import BaseLoader

try:
    from deepgram import DeepgramClient, PrerecordedOptions
except ImportError:
    raise ImportError(
        "Audio file requires extra dependencies. Install with `pip install deepgram-sdk==3.2.7`"
    ) from None


@register_deserializable
class AudioLoader(BaseLoader):
    def __init__(self):
        if not os.environ.get("DEEPGRAM_API_KEY"):
            raise ValueError("DEEPGRAM_API_KEY is not set")

        DG_KEY = os.environ.get("DEEPGRAM_API_KEY")
        self.client = DeepgramClient(DG_KEY)

    def load_data(self, url: str):
        """Load data from a audio file or URL."""

        options = PrerecordedOptions(
            model="nova-2",
            smart_format=True,
        )
        if validators.url(url):
            source = {"url": url}
            response = self.client.listen.prerecorded.v("1").transcribe_url(source, options)
        else:
            with open(url, "rb") as audio:
                source = {"buffer": audio}
                response = self.client.listen.prerecorded.v("1").transcribe_file(source, options)
        content = response["results"]["channels"][0]["alternatives"][0]["transcript"]

        doc_id = hashlib.sha256((content + url).encode()).hexdigest()
        metadata = {"url": url}

        return {
            "doc_id": doc_id,
            "data": [
                {
                    "content": content,
                    "meta_data": metadata,
                }
            ],
        }
