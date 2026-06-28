"""Regression tests for ``PlatformBackend`` multi-entity delete behavior.

Covers #5935: ``delete_entities()`` used to reassign a single ``result``
variable each pass, so only the last entity's API response was returned.
The fix keys responses by entity type so multi-entity deletes preserve
every response.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from mem0_cli.backend.platform import PlatformBackend
from mem0_cli.config import PlatformConfig


def _make_backend_with_request_sequence(responses: list[dict]) -> PlatformBackend:
    """Build a ``PlatformBackend`` whose ``_request`` returns each response in turn."""
    backend = PlatformBackend(PlatformConfig(api_key="test-key"))
    mock_request = MagicMock(side_effect=list(responses))
    # Patch the bound method on the instance.
    backend._request = mock_request  # type: ignore[method-assign]
    return backend


def test_delete_entities_single_returns_keyed_response():
    """A single-entity delete returns ``{entity_type: response}``."""
    backend = _make_backend_with_request_sequence([{"message": "Entity deleted"}])
    result = backend.delete_entities(user_id="alice")
    assert result == {"user": {"message": "Entity deleted"}}


def test_delete_entities_multi_preserves_every_response():
    """Multi-entity delete returns one entry per entity, keyed by type.

    Regression for #5935: the previous implementation reassigned a single
    ``result`` variable each iteration and returned only the final response,
    silently dropping the others.
    """
    backend = _make_backend_with_request_sequence(
        [
            {"message": "User deleted", "id": "alice"},
            {"message": "Agent deleted", "id": "bot1"},
            {"message": "App deleted", "id": "app-x"},
        ]
    )
    result = backend.delete_entities(user_id="alice", agent_id="bot1", app_id="app-x")

    # All three responses are preserved, keyed by entity type.
    assert set(result.keys()) == {"user", "agent", "app"}
    assert result["user"] == {"message": "User deleted", "id": "alice"}
    assert result["agent"] == {"message": "Agent deleted", "id": "bot1"}
    assert result["app"] == {"message": "App deleted", "id": "app-x"}

    # And we actually issued one DELETE per entity.
    assert backend._request.call_count == 3  # type: ignore[attr-defined]


def test_delete_entities_no_entities_raises():
    """No entity IDs provided raises ``ValueError``."""
    backend = _make_backend_with_request_sequence([])
    try:
        backend.delete_entities()
    except ValueError as e:
        assert "entity id" in str(e).lower()
    else:
        raise AssertionError("delete_entities() should raise ValueError when no IDs are given")
