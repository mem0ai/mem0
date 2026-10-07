"""Memory content must never reach the application log.

See https://github.com/mem0ai/mem0/issues/6915
"""

import hashlib
import logging
from unittest.mock import MagicMock, patch

import pytest

from mem0 import Memory
from mem0.memory.main import _content_hash, _describe_message

SECRET = "I have type 2 diabetes and take metformin daily"


@pytest.fixture
def memory():
    with patch.object(Memory, "__init__", return_value=None):
        instance = Memory()

    existing = MagicMock()
    existing.payload = {"data": "an older memory", "created_at": "2024-01-01T00:00:00+00:00"}

    instance.vector_store = MagicMock()
    instance.vector_store.get.return_value = existing
    instance.embedding_model = MagicMock()
    instance.embedding_model.embed.return_value = [0.1, 0.2, 0.3]
    instance.db = MagicMock()
    instance._remove_memory_from_entity_store = MagicMock()
    instance._link_entities_for_memory = MagicMock()
    return instance


def test_update_memory_does_not_log_content(memory, caplog):
    with caplog.at_level(logging.DEBUG, logger="mem0.memory.main"):
        memory._update_memory("mem-1", SECRET, {})

    messages = [record.message for record in caplog.records]
    assert messages, "expected the update to log something"
    assert not any(SECRET in message for message in messages)
    # the hash still lets an operator match the log line to the stored record
    assert any(hashlib.md5(SECRET.encode()).hexdigest() in message for message in messages)


def test_create_memory_does_not_log_content(memory, caplog):
    memory.db.add_history = MagicMock()

    with caplog.at_level(logging.DEBUG, logger="mem0.memory.main"):
        memory._create_memory(SECRET, {})

    assert not any(SECRET in record.message for record in caplog.records)


def test_invalid_message_is_logged_by_shape_only(memory, caplog):
    memory.vector_store.insert = MagicMock()

    with caplog.at_level(logging.WARNING, logger="mem0.memory.main"):
        memory._add_to_vector_store(
            [{"content": "my social security number is 078-05-1120"}],
            metadata={},
            filters={},
            infer=False,
        )

    warnings = [record.message for record in caplog.records if record.levelno == logging.WARNING]
    assert any("Skipping invalid message format" in message for message in warnings)
    assert not any("078-05-1120" in message for message in warnings)
    assert any("keys ['content']" in message for message in warnings)


def test_content_hash_matches_the_stored_hash():
    assert _content_hash(SECRET) == hashlib.md5(SECRET.encode()).hexdigest()
    assert _content_hash(None) == "none"


def test_describe_message_keeps_keys_and_drops_values():
    described = _describe_message({"role": "user", "content": SECRET})

    assert "role" in described
    assert "content" in described
    assert SECRET not in described
    assert _describe_message("not a dict") == "str"
