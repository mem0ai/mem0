"""Tests for the store's anonymous usage telemetry."""

from unittest.mock import MagicMock, patch

import pytest

from mem0_strands import Mem0MemoryStore, telemetry


@pytest.fixture
def mock_client():
    """A mocked Mem0ServiceClient that looks like the hosted platform."""
    client = MagicMock()
    client.is_platform = True
    client.mem0.user_email = "dev@example.com"
    return client


@pytest.fixture
def captured():
    """Intercept the SDK PostHog client and collect (event, properties, distinct_id)."""
    with patch.object(telemetry, "client_telemetry") as posthog:
        events = []
        posthog.capture_event.side_effect = lambda event, properties, distinct_id=None: events.append(
            (event, properties, distinct_id)
        )
        yield events


def make_store(mock_client, **kwargs):
    kwargs.setdefault("user_id", "alex")
    return Mem0MemoryStore(client=mock_client, **kwargs)


# ---------------------------------------------------------------------------
# Event shape
# ---------------------------------------------------------------------------


def test_every_event_carries_source_and_backend(mock_client, captured):
    assert make_store(mock_client).client is mock_client

    event, properties, distinct_id = captured[0]
    assert event == "strands.store.init"
    assert properties["source"] == "STRANDS"
    assert properties["language"] == "python"
    assert properties["backend"] == "platform"
    assert properties["strands_store_version"]
    assert distinct_id == "dev@example.com"


def test_oss_backend_is_labelled_and_falls_back_to_the_sdk_anonymous_id(captured):
    client = MagicMock()
    client.is_platform = False
    del client.mem0.user_email
    assert make_store(client).client is client

    _, properties, distinct_id = captured[0]
    assert properties["backend"] == "oss"
    assert distinct_id is None


def test_init_is_recorded_once_per_store(mock_client, captured):
    store = make_store(mock_client)
    assert store.client is store.client

    assert [event for event, _, _ in captured] == ["strands.store.init"]


def test_init_describes_configuration_without_scope_values(mock_client, captured):
    store = make_store(mock_client, agent_id="assistant", writable=False, extraction=True, metadata={"team": "core"})
    assert store.client is mock_client

    _, properties, _ = captured[0]
    assert properties["scopes"] == ["agent_id", "user_id"]
    assert properties["writable"] is False
    assert properties["extraction_enabled"] is True
    assert properties["has_default_metadata"] is True
    assert "alex" not in str(properties)
    assert "assistant" not in str(properties)
    assert "core" not in str(properties)


# ---------------------------------------------------------------------------
# Per-operation events
# ---------------------------------------------------------------------------


async def test_search_records_counts_but_never_the_query(mock_client, captured):
    mock_client.search_memories.return_value = [{"id": "m1", "memory": "Likes tea"}]

    await make_store(mock_client).search("what does alex drink")

    event, properties, _ = captured[-1]
    assert event == "strands.store.search"
    assert properties["success"] is True
    assert properties["result_count"] == 1
    assert properties["top_k"] == 5
    assert properties["duration_ms"] >= 0
    assert "drink" not in str(properties)
    assert "tea" not in str(properties)


async def test_add_records_size_but_never_the_content(mock_client, captured):
    await make_store(mock_client).add("Alex prefers dark roast", metadata={"team": "core"})

    event, properties, _ = captured[-1]
    assert event == "strands.store.add"
    assert properties["success"] is True
    assert properties["content_chars"] == len("Alex prefers dark roast")
    assert properties["has_metadata"] is True
    assert "roast" not in str(properties)


async def test_add_messages_records_turn_counts_but_never_the_turns(mock_client, captured):
    messages = [
        {"role": "user", "content": [{"text": "hello"}]},
        {"role": "assistant", "content": [{"text": "hi there"}]},
    ]

    await make_store(mock_client).add_messages(messages)

    event, properties, _ = captured[-1]
    assert event == "strands.store.add_messages"
    assert properties["message_count"] == 2
    assert properties["rendered_count"] == 2
    assert properties["total_chars"] == len("hello") + len("hi there")
    assert "hello" not in str(properties)


async def test_empty_add_messages_records_nothing(mock_client, captured):
    assert await make_store(mock_client).add_messages([]) is None
    assert [event for event, _, _ in captured] == []


# ---------------------------------------------------------------------------
# Failures
# ---------------------------------------------------------------------------


async def test_a_failed_search_records_a_coarse_error_kind_and_still_raises(mock_client, captured):
    mock_client.search_memories.side_effect = RuntimeError("HTTP 429 rate limit exceeded for key sk-secret")

    with pytest.raises(RuntimeError):
        await make_store(mock_client).search("anything")

    event, properties, _ = captured[-1]
    assert event == "strands.store.search"
    assert properties["success"] is False
    assert properties["error_kind"] == "rate-limited"
    assert "sk-secret" not in str(properties)


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("request timed out", "timeout"),
        ("401 Unauthorized", "auth"),
        ("429 Too Many Requests", "rate-limited"),
        ("503 Service Unavailable", "server-error"),
        ("422 Unprocessable Entity", "bad-request"),
        ("something else entirely", "ValueError"),
    ],
)
def test_error_kind_buckets_failures(message, expected):
    assert telemetry.error_kind(ValueError(message)) == expected


def test_a_broken_telemetry_backend_never_breaks_the_store(mock_client):
    with patch.object(telemetry, "client_telemetry") as posthog:
        posthog.capture_event.side_effect = RuntimeError("posthog is down")
        assert make_store(mock_client).client is mock_client
