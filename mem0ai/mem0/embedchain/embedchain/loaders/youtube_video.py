import hashlib
import json
import logging

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    raise ImportError("YouTube video requires extra dependencies. Install with `pip install youtube-transcript-api`")
try:
    from langchain_community.document_loaders import YoutubeLoader
    from langchain_community.document_loaders.youtube import _parse_video_id
except ImportError:
    raise ImportError("YouTube video requires extra dependencies. Install with `pip install pytube==15.0.0`") from None
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.loaders.base_loader import BaseLoader
from embedchain.utils.misc import clean_string


@register_deserializable
class YoutubeVideoLoader(BaseLoader):
    def load_data(self, url):
        """Load data from a Youtube video."""
        video_id = _parse_video_id(url)

        languages = ["en"]
        try:
            # Fetching transcript data
            languages = [transcript.language_code for transcript in YouTubeTranscriptApi.list_transcripts(video_id)]
            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=languages)
            # convert transcript to json to avoid unicode symboles
            transcript = json.dumps(transcript, ensure_ascii=True)
        except Exception:
            logging.exception(f"Failed to fetch transcript for video {url}")
            transcript = "Unavailable"

        loader = YoutubeLoader.from_youtube_url(url, add_video_info=True, language=languages)
        doc = loader.load()
        output = []
        if not len(doc):
            raise ValueError(f"No data found for url: {url}")
        content = doc[0].page_content
        content = clean_string(content)
        metadata = doc[0].metadata
        metadata["url"] = url
        metadata["transcript"] = transcript

        output.append(
            {
                "content": content,
                "meta_data": metadata,
            }
        )
        doc_id = hashlib.sha256((content + url).encode()).hexdigest()
        return {
            "doc_id": doc_id,
            "data": output,
        }
