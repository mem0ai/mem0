import concurrent.futures
import hashlib
import logging


from embedchain.loaders.base_loader import BaseLoader
from embedchain.loaders.youtube_video import YoutubeVideoLoader


class YoutubeChannelLoader(BaseLoader):
    """Loader for youtube channel."""

    def load_data(self, channel_name):
        # Check if dependencies are installed at the beginning
        try:
            import yt_dlp
        except ImportError as e:
            raise ValueError(
                "YoutubeLoader requires extra dependencies. Install with `pip install --upgrade 'embedchain[youtube_channel]'`"  # noqa: E501
            ) from e

        youtube_url = f"https://www.youtube.com/{channel_name}/videos"
        youtube_video_loader = YoutubeVideoLoader()

        def _get_vid_urls():
            ydl_opts = {"quiet": True, "extract_flat": True}
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info_dict = ydl.extract_info(youtube_url, download=False)
                    return [entry["url"] for entry in info_dict.get("entries", [])]
            except Exception:
                logging.error(f"Failed to fetch Youtube videos for channel: {channel_name}")
                return []

        def _load_vids(video_links):
            result = []
            result_urls = []

            def worker(video_link):
                try:
                    each_load_data = youtube_video_loader.load_data(video_link)
                    data = each_load_data.get("data")
                    if data:
                        result.extend(data)
                        result_urls.extend([datum.get("meta_data").get("url") for datum in data])
                except Exception as e:
                    logging.error(f"Failed to load youtube video {video_link}: {e}")

            with concurrent.futures.ThreadPoolExecutor() as executor:
                list(executor.map(worker, video_links))

            return result, result_urls

        video_links = _get_vid_urls()
        logging.info("Loading videos from youtube channel...")

        data, data_urls = _load_vids(video_links)

        doc_id = hashlib.sha256((youtube_url + ", ".join(data_urls)).encode()).hexdigest()

        return {"doc_id": doc_id, "data": data}
