import pytest

from mem0.exceptions import ValidationError as Mem0ValidationError
from mem0.memory.main import _build_filters_and_metadata


def test_build_filters_requires_session_id():
    with pytest.raises(Mem0ValidationError) as excinfo:
        _build_filters_and_metadata()

    assert excinfo.value.error_code == "VALIDATION_001"


def test_build_filters_merges_metadata_and_filters():
    input_metadata = {"foo": "bar"}
    input_filters = {"baz": "qux", "actor_id": "actor-from-filter"}

    metadata, filters = _build_filters_and_metadata(
        user_id="user-123", input_metadata=input_metadata, input_filters=input_filters
    )

    assert metadata == {"foo": "bar", "user_id": "user-123"}
    assert filters == {"baz": "qux", "actor_id": "actor-from-filter", "user_id": "user-123"}
    assert input_metadata == {"foo": "bar"}
    assert input_filters == {"baz": "qux", "actor_id": "actor-from-filter"}


def test_build_filters_actor_id_argument_wins():
    input_filters = {"actor_id": "actor-from-filter"}

    metadata, filters = _build_filters_and_metadata(
        user_id="user-123", actor_id="actor-from-arg", input_filters=input_filters
    )

    assert metadata == {"user_id": "user-123"}
    assert filters["actor_id"] == "actor-from-arg"
    assert "actor_id" not in metadata
    assert input_filters == {"actor_id": "actor-from-filter"}


def test_build_filters_multiple_session_ids():
    metadata, filters = _build_filters_and_metadata(
        user_id="user-123", agent_id="agent-456", run_id="run-789"
    )

    assert metadata == {"user_id": "user-123", "agent_id": "agent-456", "run_id": "run-789"}
    assert filters == {"user_id": "user-123", "agent_id": "agent-456", "run_id": "run-789"}
