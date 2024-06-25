import hashlib
import json
from unittest.mock import patch

import pytest
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi

from embedchain.loaders.youtube_video import YoutubeVideoLoader  # Adjust the import according to your module structure

@pytest.fixture
def youtube_video_loader():
    return YoutubeVideoLoader()

def test_load_data(youtube_video_loader):
    video_url = "https://www.youtube.com/watch?v=VIDEO_ID"
    mock_result = {
        'title': 'Test Video',
        'uploader': 'Uploader Name',
        'upload_date': '20200101',
        'duration': 3600,
        'view_count': 1000,
        'like_count': 100,
        'dislike_count': 10,
        'average_rating': 4.5,
        'categories': ['Education'],
        'tags': ['tag1', 'tag2'],
        'id': 'VIDEO_ID'
    }
    mock_transcript = [{"text": "sample text", "start": 0.0, "duration": 5.0}]
    serialized_transcript = json.dumps(mock_transcript, ensure_ascii=False)  # Serialize the transcript for the test
    content = ' '.join([item['text'] for item in mock_transcript])

    with patch.object(yt_dlp.YoutubeDL, 'extract_info', return_value=mock_result), \
         patch.object(YouTubeTranscriptApi, 'get_transcript', return_value=mock_transcript):
        result = youtube_video_loader.load_data(video_url)

    expected_doc_id = hashlib.sha256((content + video_url).encode()).hexdigest()
    expected_data = [{
        "content": content,
        "meta_data": {
            "title": mock_result['title'],
            "uploader": mock_result['uploader'],
            "upload_date": '20200101',  # Keep as is, matching the `load_data` method
            "duration": mock_result['duration'],
            "view_count": mock_result['view_count'],
            "like_count": mock_result['like_count'],
            "dislike_count": mock_result['dislike_count'],
            "average_rating": mock_result['average_rating'],
            "categories": mock_result['categories'],
            "tags": mock_result['tags'],
            "url": video_url,
            "transcript": serialized_transcript  # Use the serialized transcript here
        }
    }]

    assert result['doc_id'] == expected_doc_id
    assert result['data'] == expected_data

def test_load_data_with_empty_doc(youtube_video_loader):
    video_url = "https://www.youtube.com/watch?v=VIDEO_ID"
    with patch.object(yt_dlp.YoutubeDL, 'extract_info', return_value={'entries': []}):
        with pytest.raises(ValueError):
            youtube_video_loader.load_data(video_url)
