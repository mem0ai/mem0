import hashlib
import json
import logging

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    raise ImportError('YouTube video requires extra dependencies. Install with `pip install youtube-transcript-api "`')
try:
    import yt_dlp
except ImportError:
    raise ImportError(
        'YouTube video requires extra dependencies. Install with `pip install yt-dlp`'
    ) from None
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.loaders.base_loader import BaseLoader

@register_deserializable
class YoutubeVideoLoader(BaseLoader):
    def load_data(self, url):
        """Load data from a Youtube video using yt-dlp."""
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en'],
            'subtitlesformat': 'json'
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(url, download=False)
            if not result or 'entries' in result and not result['entries']:
                raise ValueError(f"No data found for url: {url}")

        metadata = {
            'title': result.get('title'),
            'uploader': result.get('uploader'),
            'upload_date': result.get('upload_date'),
            'duration': result.get('duration'),
            'view_count': result.get('view_count'),
            'like_count': result.get('like_count'),
            'dislike_count': result.get('dislike_count'),
            'average_rating': result.get('average_rating'),
            'categories': result.get('categories'),
            'tags': result.get('tags'),
            'url': url
        }
        content = ''
        video_id = url.split("v=")[1].split("&")[0]
        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=["en"])
            content = ' '.join([item['text'] for item in transcript])
            metadata["transcript"] = json.dumps(transcript, ensure_ascii=False)
        except Exception:
            logging.exception(f"Failed to fetch transcript for video {url}")
            metadata["transcript"] = "Unavailable"
        
        output = [{
            "content": content,
            "meta_data": metadata,
        }]
        
        doc_id = hashlib.sha256((content + url).encode()).hexdigest()
        return {
            "doc_id": doc_id,
            "data": output,
        }
