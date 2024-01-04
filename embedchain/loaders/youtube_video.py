import hashlib
import requests
import os
from dotenv import load_dotenv


load_dotenv()

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
            transcription_url = "https://transcript.lol/api/createTranscript"
            payload = {
                "sourceUrl": f"{url}",
                "transcriptLangCode": "es"
            }
            headers = {
                "X-API-KEY": os.environ['Transcript_API_Key'],
                "Content-Type": "application/json"
            }
            response = requests.request("POST", transcription_url, json=payload, headers=headers)
            content = response.text
            meta_data = {}
        else:
            content = doc[0].page_content
            meta_data = doc[0].metadata
        content = clean_string(content)
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
