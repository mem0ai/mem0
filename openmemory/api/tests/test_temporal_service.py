"""Tests for temporal service."""
import pytest
import sys
from pathlib import Path
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from services.temporal_service import (
    build_temporal_extraction_prompt,
    format_temporal_log_string,
    enrich_metadata_with_mycelia_fields,
)


def test_build_temporal_extraction_prompt():
    """Test that prompt includes current date context."""
    test_date = datetime(2025, 12, 25, 14, 30, 0)
    prompt = build_temporal_extraction_prompt(test_date)

    assert "2025-12-25" in prompt
    assert "14:30:00" in prompt
    assert "Wednesday" in prompt or test_date.strftime("%A") in prompt
    assert "isEvent" in prompt
    assert "isPerson" in prompt
    assert "timeRanges" in prompt


def test_format_temporal_log_string_with_data():
    """Test formatting temporal info for logging."""
    temporal_info = {
        "emoji": "📅",
        "isEvent": True,
        "entities": ["Alice", "Bob"]
    }

    result = format_temporal_log_string(temporal_info)

    assert "emoji=📅" in result
    assert "isEvent=True" in result
    assert "entities=2" in result


def test_format_temporal_log_string_none():
    """Test formatting with None temporal info."""
    result = format_temporal_log_string(None)
    assert result == ""


def test_format_temporal_log_string_empty():
    """Test formatting with empty temporal info."""
    result = format_temporal_log_string({})
    assert "emoji=None" in result or "emoji=" in result


@pytest.mark.asyncio
async def test_enrich_metadata_with_mycelia_fields_no_temporal():
    """Test metadata enrichment when temporal extraction returns None."""
    mock_client = Mock()

    with patch('services.temporal_service.extract_temporal_entity', return_value=None):
        base_metadata = {"user_id": "test"}
        enriched, temporal_info = await enrich_metadata_with_mycelia_fields(
            mock_client,
            "Some fact",
            base_metadata
        )

        assert enriched == base_metadata
        assert temporal_info is None


@pytest.mark.asyncio
async def test_enrich_metadata_with_mycelia_fields_with_data():
    """Test metadata enrichment with full temporal data."""
    mock_client = Mock()
    mock_temporal = {
        "isEvent": True,
        "isPerson": True,
        "isPlace": False,
        "isPromise": False,
        "isRelationship": False,
        "entities": ["Alice"],
        "timeRanges": [],
        "emoji": "📅"
    }

    with patch('services.temporal_service.extract_temporal_entity', return_value=mock_temporal):
        base_metadata = {"user_id": "test"}
        enriched, temporal_info = await enrich_metadata_with_mycelia_fields(
            mock_client,
            "Meeting with Alice",
            base_metadata
        )

        assert enriched["isEvent"] == True
        assert enriched["isPerson"] == True
        assert enriched["emoji"] == "📅"
        assert enriched["entities"] == ["Alice"]
        assert "display_name" in enriched
        assert "📅" in enriched["display_name"]
        assert temporal_info == mock_temporal


@pytest.mark.asyncio
async def test_enrich_metadata_preserves_base():
    """Test that base metadata is preserved during enrichment."""
    mock_client = Mock()
    mock_temporal = {
        "isEvent": False,
        "isPerson": False,
        "isPlace": False,
        "isPromise": False,
        "isRelationship": False,
        "entities": [],
        "timeRanges": [],
        "emoji": None
    }

    with patch('services.temporal_service.extract_temporal_entity', return_value=mock_temporal):
        base_metadata = {"user_id": "test", "custom_field": "preserved"}
        enriched, _ = await enrich_metadata_with_mycelia_fields(
            mock_client,
            "Fact",
            base_metadata
        )

        # Base metadata should be preserved
        assert enriched["user_id"] == "test"
        assert enriched["custom_field"] == "preserved"
        # Temporal fields should be added
        assert "isEvent" in enriched
        assert "isPerson" in enriched
