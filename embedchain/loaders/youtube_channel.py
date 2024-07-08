import concurrent.futures
import hashlib
import logging

from tqdm import tqdm

from embedchain.loaders.base_loader import BaseLoader
from embedchain.loaders.youtube_video import YoutubeVideoLoader

logger = logging.getLogger(__name__)


class YoutubeChannelLoader(BaseLoader):
    """Loader for youtube channel."""

    def load_data(self, channel_name):
        try:
            import yt_dlp
        except ImportError as e:
            raise ValueError(
                "YoutubeChannelLoader requires extra dependencies. Install with `pip install yt_dlp==2023.11.14 youtube-transcript-api==0.6.1`"  # noqa: E501
            ) from e

        data = []
        data_urls = []
        youtube_url = f"https://www.youtube.com/{channel_name}/videos"
        youtube_video_loader = YoutubeVideoLoader()

        def _get_yt_video_links():
            try:
                ydl_opts = {
                    "quiet": True,
                    "extract_flat": True,
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info_dict = ydl.extract_info(youtube_url, download=False)
                    if "entries" in info_dict:
                        videos = [entry["url"] for entry in info_dict["entries"]]
                        return videos
            except Exception:
                logger.error(f"Failed to fetch youtube videos for channel: {channel_name}")
                return []

        def _load_yt_video(video_link):
            try:
                each_load_data = youtube_video_loader.load_data(video_link)
                if each_load_data:
                    return each_load_data.get("data")
            except Exception as e:
                logger.error(f"Failed to load youtube video {video_link}: {e}")
            return None

        def _add_youtube_channel():
            video_links = _get_yt_video_links()
            logger.info("Loading videos from youtube channel...")
            with concurrent.futures.ThreadPoolExecutor() as executor:
                # Submitting all tasks and storing the future object with the video link
                future_to_video = {
                    executor.submit(_load_yt_video, video_link): video_link for video_link in video_links
                }

                for future in tqdm(
                    concurrent.futures.as_completed(future_to_video), total=len(video_links), desc="Processing videos"
                ):
                    video = future_to_video[future]
                    try:
                        results = future.result()
                        if results:
                            data.extend(results)
                            data_urls.extend([result.get("meta_data").get("url") for result in results])
                    except Exception as e:
                        logger.error(f"Failed to process youtube video {video}: {e}")

        _add_youtube_channel()
        doc_id = hashlib.sha256((youtube_url + ", ".join(data_urls)).encode()).hexdigest()
        return {
            "doc_id": doc_id,
            "data": data,
        }
