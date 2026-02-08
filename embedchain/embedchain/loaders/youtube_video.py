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
        """Load data from a Youtube video with improved metadata handling."""
        import datetime
        from dateutil import parser, tz

        video_id = _parse_video_id(url)

        # ------------------------------------------------------
        # 1) TRANSCRIPT FETCHING
        # ------------------------------------------------------
        languages = ["en"]
        try:
            languages = [
                transcript.language_code
                for transcript in YouTubeTranscriptApi.list_transcripts(video_id)
            ]
            transcript_data = YouTubeTranscriptApi.get_transcript(
                video_id, languages=languages
            )
            transcript = json.dumps(transcript_data, ensure_ascii=True)
        except Exception:
            logging.exception(f"Failed to fetch transcript for video {url}")
            transcript = "Unavailable"

        # ------------------------------------------------------
        # 2) LOAD VIDEO METADATA (using LangChain loader)
        # ------------------------------------------------------
        loader = YoutubeLoader.from_youtube_url(
            url, add_video_info=True, language=languages
        )
        doc = loader.load()

        if not len(doc):
            raise ValueError(f"No data found for url: {url}")

        content = clean_string(doc[0].page_content)
        metadata = doc[0].metadata
        metadata["url"] = url
        metadata["transcript"] = transcript

        # ------------------------------------------------------
        # 3) PUBLISH TIME FIX — ISO 8601 + UTC NORMALIZATION
        # ------------------------------------------------------
        publish_time = metadata.get("publish_date") or metadata.get("publish_date_utc") \
                       or metadata.get("publishedAt") or metadata.get("pubDate")

        try:
            if publish_time:
                # Convert to datetime
                dt = parser.parse(str(publish_time))

                # Normalize timezone to UTC
                if not dt.tzinfo:
                    dt = dt.replace(tzinfo=tz.UTC)
                dt_utc = dt.astimezone(tz.UTC)

                # Full ISO 8601 format
                metadata["published_at_iso"] = dt_utc.isoformat()
            else:
                metadata["published_at_iso"] = None
        except Exception as e:
            logging.error(f"Failed to parse publish time for {url}: {e}")
            metadata["published_at_iso"] = None

        # ------------------------------------------------------
        # 4) DURATION + THUMBNAILS (if missing)
        # ------------------------------------------------------
        metadata.setdefault("duration", metadata.get("length") or metadata.get("lengthSeconds"))
        metadata.setdefault("thumbnail_url", metadata.get("thumbnail_url") or metadata.get("thumbnails"))

        # ------------------------------------------------------
        # 5) FINAL OUTPUT
        # ------------------------------------------------------
        output = [
            {
                "content": content,
                "meta_data": metadata,
            }
        ]

        doc_id = hashlib.sha256((content + url).encode()).hexdigest()

        return {
            "doc_id": doc_id,
            "data": output,
        }
