"""Essential tests for message parsing utilities."""

import pytest
from unittest.mock import patch
from mem0.memory.utils import parse_messages, parse_vision_messages


class TestParseMessages:
    """Test the parse_messages utility function."""

    def test_parse_basic_messages(self):
        """Test parsing basic message types."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
            {"role": "system", "content": "You are helpful"}
        ]
        result = parse_messages(messages)
        
        assert "user: Hello" in result
        assert "assistant: Hi there" in result
        assert "system: You are helpful" in result

    def test_parse_empty_messages(self):
        """Test parsing empty messages list."""
        result = parse_messages([])
        assert result == ""

    def test_parse_messages_with_missing_fields(self):
        """Test parsing messages with missing fields."""
        # Test missing role - should raise KeyError
        with pytest.raises(KeyError):
            parse_messages([{"content": "Missing role"}])
        
        # Test missing content - should raise KeyError  
        with pytest.raises(KeyError):
            parse_messages([{"role": "user"}])
        
        # Test invalid role - should be processed but not included
        messages = [{"role": "invalid_role", "content": "Invalid role"}]
        result = parse_messages(messages)
        assert result == ""

    def test_parse_messages_with_special_content(self):
        """Test parsing messages with special content."""
        messages = [
            {"role": "user", "content": "Hello 世界! 🚀"},
            {"role": "user", "content": "```python\ndef hello():\n    pass\n```"}
        ]
        result = parse_messages(messages)
        assert "Hello 世界! 🚀" in result
        assert "```python" in result


class TestParseVisionMessages:
    """Test the parse_vision_messages utility function."""

    def test_parse_regular_messages(self):
        """Test parsing regular text messages."""
        messages = [{"role": "user", "content": "Hello"}]
        result = parse_vision_messages(messages)
        assert result == messages

    def test_parse_vision_messages_with_image(self):
        """Test parsing vision messages with image URL."""
        messages = [{
            "role": "user",
            "content": {
                "type": "image_url",
                "image_url": {"url": "https://example.com/image.jpg"}
            }
        }]
        
        with patch('mem0.memory.utils.get_image_description') as mock_get_desc:
            mock_get_desc.return_value = "Image description"
            result = parse_vision_messages(messages)
            
            assert result[0]["content"] == "Image description"

    def test_parse_vision_messages_download_error(self):
        """Test parsing vision messages when image download fails."""
        messages = [{
            "role": "user",
            "content": {
                "type": "image_url",
                "image_url": {"url": "https://invalid.com/image.jpg"}
            }
        }]
        
        with patch('mem0.memory.utils.get_image_description') as mock_get_desc:
            mock_get_desc.side_effect = Exception("Download failed")
            
            with pytest.raises(Exception) as exc_info:
                parse_vision_messages(messages)
            
            assert "Error while downloading" in str(exc_info.value)
