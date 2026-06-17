import logging
from unittest.mock import Mock

from mem0.memory.main import (
    ADD_CONTEXT_SEARCH_MAX_CHARS,
    ADD_MAX_ENTITY_LINKS_PER_EVENT,
    ADD_MAX_EXTRACTED_MEMORIES,
    ADD_MEMORY_EMBEDDING_MAX_CHARS,
    Memory,
    SEARCH_QUERY_MAX_CHARS,
    _cap_entity_keys,
    _cap_extracted_memories,
    _cap_memory_embedding_texts,
    _tail_cap_text,
)


def test_tail_cap_text_keeps_recent_suffix():
    text = "old-" + ("x" * ADD_CONTEXT_SEARCH_MAX_CHARS)

    capped = _tail_cap_text(text, ADD_CONTEXT_SEARCH_MAX_CHARS)

    assert capped == text[-ADD_CONTEXT_SEARCH_MAX_CHARS:]


def test_cap_extracted_memories_keeps_last_memories(caplog):
    memories = [{"text": f"memory-{i}"} for i in range(ADD_MAX_EXTRACTED_MEMORIES + 3)]

    with caplog.at_level(logging.WARNING):
        capped = _cap_extracted_memories(memories)

    assert capped == memories[-ADD_MAX_EXTRACTED_MEMORIES:]
    assert any("Extracted memory cap applied" in record.message for record in caplog.records)


def test_cap_memory_embedding_texts_keeps_original_text_untouched(caplog):
    original = "old-" + ("z" * ADD_MEMORY_EMBEDDING_MAX_CHARS)

    with caplog.at_level(logging.WARNING):
        capped = _cap_memory_embedding_texts([original])

    assert capped == [original[-ADD_MEMORY_EMBEDDING_MAX_CHARS:]]
    assert original.startswith("old-")
    assert any("Memory embedding input cap applied" in record.message for record in caplog.records)


def test_cap_entity_keys_keeps_first_100_entities(caplog):
    keys = [f"entity-{i}" for i in range(ADD_MAX_ENTITY_LINKS_PER_EVENT + 3)]

    with caplog.at_level(logging.WARNING):
        capped = _cap_entity_keys(keys)

    assert capped == keys[:ADD_MAX_ENTITY_LINKS_PER_EVENT]
    assert any("ADD entity-linking cap applied" in record.message for record in caplog.records)


def test_search_vector_store_caps_query_before_embedding():
    memory = object.__new__(Memory)
    memory.embedding_model = Mock()
    memory.embedding_model.embed.return_value = [0.1, 0.2, 0.3]
    memory.vector_store = Mock()
    memory.vector_store.search.return_value = []
    memory.vector_store.keyword_search.return_value = None
    memory._compute_entity_boosts = Mock(return_value={})
    query = "old-" + ("q" * SEARCH_QUERY_MAX_CHARS)

    Memory._search_vector_store(memory, query, filters={}, limit=5)

    memory.embedding_model.embed.assert_called_once_with(query[-SEARCH_QUERY_MAX_CHARS:], "search")
