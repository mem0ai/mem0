"""Tests for Pydantic schemas."""
import pytest
import sys
from pathlib import Path
from datetime import datetime
from pydantic import ValidationError

# Import directly from schemas file to avoid SQLAlchemy import issues
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))
from models.schemas import (
    TimeRange,
    TemporalEntity,
    CreateMemoryRequest,
    DeleteMemoriesRequest,
    PauseMemoriesRequest,
    UpdateMemoryRequest,
    MoveMemoriesRequest,
    FilterMemoriesRequest,
)


def test_time_range_valid():
    """Test TimeRange model with valid data."""
    tr = TimeRange(
        start=datetime(2025, 12, 25, 10, 0, 0),
        end=datetime(2025, 12, 25, 12, 0, 0),
        name="Test Event"
    )
    assert tr.name == "Test Event"
    assert tr.start < tr.end


def test_temporal_entity_defaults():
    """Test TemporalEntity with default values."""
    te = TemporalEntity(
        isEvent=False,
        isPerson=False,
        isPlace=False,
        isPromise=False,
        isRelationship=False
    )
    assert te.entities == []
    assert te.timeRanges == []
    assert te.emoji is None


def test_temporal_entity_full():
    """Test TemporalEntity with all fields."""
    te = TemporalEntity(
        isEvent=True,
        isPerson=True,
        isPlace=False,
        isPromise=False,
        isRelationship=False,
        entities=["Alice", "Bob"],
        timeRanges=[
            TimeRange(
                start=datetime(2025, 12, 25, 10, 0, 0),
                end=datetime(2025, 12, 25, 12, 0, 0)
            )
        ],
        emoji="🎉"
    )
    assert len(te.entities) == 2
    assert len(te.timeRanges) == 1
    assert te.emoji == "🎉"


def test_create_memory_request_minimal():
    """Test CreateMemoryRequest with minimal required fields."""
    req = CreateMemoryRequest(
        user_id="test_user",
        text="Test memory"
    )
    assert req.user_id == "test_user"
    assert req.text == "Test memory"
    assert req.infer == True  # Default
    assert req.app == "openmemory"  # Default
    assert req.metadata == {}


def test_create_memory_request_full():
    """Test CreateMemoryRequest with all fields."""
    req = CreateMemoryRequest(
        user_id="test_user",
        text="Test memory",
        metadata={"source": "test"},
        infer=False,
        app="custom_app",
        timestamp=1735128000
    )
    assert req.infer == False
    assert req.app == "custom_app"
    assert req.timestamp == 1735128000


def test_delete_memories_request():
    """Test DeleteMemoriesRequest validation."""
    req = DeleteMemoriesRequest(
        memory_ids=["id1", "id2", "id3"],
        user_id="test_user"
    )
    assert len(req.memory_ids) == 3


def test_pause_memories_request_defaults():
    """Test PauseMemoriesRequest with defaults."""
    req = PauseMemoriesRequest(
        memory_ids=["id1"],
        user_id="test_user"
    )
    assert req.all_for_app == False
    assert req.state == "paused"


def test_update_memory_request():
    """Test UpdateMemoryRequest validation."""
    req = UpdateMemoryRequest(
        memory_id="test-id",
        memory_content="Updated content",
        user_id="test_user"
    )
    assert req.memory_content == "Updated content"


def test_move_memories_request():
    """Test MoveMemoriesRequest validation."""
    req = MoveMemoriesRequest(memory_ids=["id1", "id2"])
    assert len(req.memory_ids) == 2


def test_filter_memories_request_minimal():
    """Test FilterMemoriesRequest with minimal fields."""
    req = FilterMemoriesRequest(user_id="test_user")
    assert req.page == 1
    assert req.size == 10
    assert req.show_archived == False


def test_filter_memories_request_full():
    """Test FilterMemoriesRequest with all fields."""
    req = FilterMemoriesRequest(
        user_id="test_user",
        page=2,
        size=20,
        search_query="test",
        app_ids=["app1", "app2"],
        category_ids=["cat1"],
        sort_column="created_at",
        sort_direction="desc",
        show_archived=True
    )
    assert req.page == 2
    assert req.size == 20
    assert req.show_archived == True
    assert len(req.app_ids) == 2


def test_create_memory_request_validation_error():
    """Test that missing required fields raise validation errors."""
    with pytest.raises(ValidationError) as exc_info:
        CreateMemoryRequest(user_id="test")  # Missing 'text' field

    errors = exc_info.value.errors()
    assert any(e['loc'] == ('text',) for e in errors)
