import hashlib
import unittest
from unittest.mock import MagicMock, Mock, patch

from embedchain.loaders.youtube_video import YoutubeVideoLoader


class TestYoutubeVideoLoader(unittest.TestCase):
    def setUp(self):
        self.loader = YoutubeVideoLoader()
        self.video_url = "https://www.youtube.com/watch?v=VIDEO_ID"

    @patch("embedchain.loaders.youtube_video.YoutubeLoader.from_youtube_url")
    def test_load_data(self, mock_youtube_loader):
        mock_loader = Mock()
        mock_page_content = "This is a YouTube video content."
        mock_loader.load.return_value = [
            MagicMock(
                page_content=mock_page_content,
                metadata={"url": self.video_url, "title": "Test Video"},
            )
        ]
        mock_youtube_loader.return_value = mock_loader

        result = self.loader.load_data(self.video_url)
        expected_doc_id = hashlib.sha256((mock_page_content + self.video_url).encode()).hexdigest()

        self.assertEqual(result["doc_id"], expected_doc_id)

        expected_data = [
            {
                "content": "This is a YouTube video content.",
                "meta_data": {"url": "https://www.youtube.com/watch?v=VIDEO_ID", "title": "Test Video"},
            }
        ]

        self.assertEqual(result["data"], expected_data)

    @patch("embedchain.loaders.youtube_video.YoutubeLoader.from_youtube_url")
    def test_load_data_with_empty_doc(self, mock_youtube_loader):
        mock_loader = Mock()
        mock_loader.load.return_value = []
        mock_youtube_loader.return_value = mock_loader

        with self.assertRaises(ValueError):
            self.loader.load_data(self.video_url)
