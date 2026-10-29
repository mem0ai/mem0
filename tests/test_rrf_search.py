"""Exercise the real sync/async search pipelines with mocked provider boundaries."""

from unittest.mock import AsyncMock, Mock

import pytest

from mem0.configs.base import MemoryConfig
from mem0.memory.main import AsyncMemory, Memory


@pytest.mark.asyncio
@pytest.mark.parametrize("memory_type", [Memory, AsyncMemory])
@pytest.mark.parametrize("offset", [10, 60])
async def test_search_uses_configured_fusion_without_extra_provider_calls(monkeypatch, memory_type, offset):
    monkeypatch.setattr("mem0.memory.main.lemmatize_for_bm25", lambda query: query)
    monkeypatch.setattr("mem0.memory.main.extract_entities", lambda query: [("PERSON", "Alice")])
    memory = memory_type.__new__(memory_type)
    memory.config = MemoryConfig(fusion_strategy="rrf", rrf_k=offset)
    memory.embedding_model = Mock()
    memory.embedding_model.embed.return_value = [0.1, 0.2]
    memory.vector_store = Mock()
    memory.vector_store.search.return_value = [
        Mock(id=key, score=score, payload={"data": key, "user_id": "user-1"})
        for key, score in (("a", 0.9), ("b", 0.8), ("c", 0.7))
    ]
    memory.vector_store.keyword_search.return_value = [
        Mock(id=key, score=score) for key, score in (("a", 9.0), ("b", 8.0), ("c", 7.0))
    ]
    entities = {"a": 0.1, "b": 0.3, "c": 0.2}
    if memory_type is AsyncMemory:
        memory._compute_entity_boosts_async = AsyncMock(return_value=entities)
        result = await memory._search_vector_store("Alice", {"user_id": "user-1"}, 2, explain=True)
        memory._compute_entity_boosts_async.assert_awaited_once()
    else:
        memory._compute_entity_boosts = Mock(return_value=entities)
        result = memory._search_vector_store("Alice", {"user_id": "user-1"}, 2, explain=True)
        memory._compute_entity_boosts.assert_called_once()

    assert [item["id"] for item in result] == ["a", "b"]
    assert result[0]["score"] == pytest.approx(2 / (offset + 1) + 1 / (offset + 3))
    assert result[0]["memory"] == "a"
    assert result[0]["user_id"] == "user-1"
    assert result[0]["score_details"]["rrf_k"] == offset
    memory.embedding_model.embed.assert_called_once_with("Alice", "search")
    memory.vector_store.search.assert_called_once_with(
        query="Alice", vectors=[0.1, 0.2], top_k=60, filters={"user_id": "user-1"}
    )
    memory.vector_store.keyword_search.assert_called_once_with(query="Alice", top_k=60, filters={"user_id": "user-1"})


@pytest.mark.asyncio
@pytest.mark.parametrize("memory_type", [Memory, AsyncMemory])
async def test_rrf_preserves_expiration_and_semantic_threshold_gates(monkeypatch, memory_type):
    monkeypatch.setattr("mem0.memory.main.lemmatize_for_bm25", lambda query: query)
    monkeypatch.setattr("mem0.memory.main.extract_entities", lambda query: [])
    memory = memory_type.__new__(memory_type)
    memory.config = MemoryConfig(fusion_strategy="rrf")
    memory.embedding_model = Mock()
    memory.vector_store = Mock()
    memory.vector_store.search.return_value = [
        Mock(id="expired", score=0.99, payload={"data": "expired", "expiration_date": "2000-01-01"}),
        Mock(id="below", score=0.05, payload={"data": "below"}),
        Mock(id="valid", score=0.8, payload={"data": "valid"}),
    ]
    memory.vector_store.keyword_search.return_value = [
        Mock(id="expired", score=99.0),
        Mock(id="below", score=90.0),
        Mock(id="keyword-only", score=80.0),
        Mock(id="valid", score=1.0),
    ]
    if memory_type is AsyncMemory:
        result = await memory._search_vector_store("query", {"user_id": "user-1"}, 10)
    else:
        result = memory._search_vector_store("query", {"user_id": "user-1"}, 10)
    assert [item["id"] for item in result] == ["valid", "below"]
    assert result[0]["score"] == pytest.approx(1 / 61 + 1 / 64)
    assert "score_details" not in result[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("memory_type", [Memory, AsyncMemory])
async def test_rrf_union_hydrates_entity_only_and_reuses_scoped_payloads(monkeypatch, memory_type):
    monkeypatch.setattr("mem0.memory.main.lemmatize_for_bm25", lambda query: query)
    monkeypatch.setattr("mem0.memory.main.extract_entities", lambda query: [("PERSON", "Alice")])
    memory = memory_type.__new__(memory_type)
    memory.config = MemoryConfig(fusion_strategy="rrf")
    memory.embedding_model = Mock()
    memory.embedding_model.embed.return_value = [0.1, 0.2]
    memory.vector_store = Mock()
    memory.vector_store.search.return_value = [
        Mock(id="outside", score=0.95, payload={"data": "outside", "user_id": "u1"}),
        Mock(id="semantic", score=0.8, payload={"data": "semantic", "user_id": "u1"}),
    ]
    memory.vector_store.keyword_search.return_value = [
        Mock(id="keyword-only", score=100.0, payload={"data": "keyword", "user_id": "u1"}),
        # The semantic result is deliberately present in this route too; it
        # must not be fetched again through the entity links.
        Mock(id="outside", score=90.0, payload={"data": "outside", "user_id": "u1"}),
    ]
    memory.vector_store.get_by_ids.return_value = [
        Mock(id="entity-only", payload={"data": "entity", "user_id": "u1"}),
    ]
    entities = {"entity-only": 0.9, "outside": 0.8}
    filters = {"user_id": "u1", "category": {"gte": 1, "lte": 2}}

    if memory_type is AsyncMemory:
        memory._compute_entity_boosts_async = AsyncMock(return_value=entities)
        result = await memory._search_vector_store("Alice", filters, 3, threshold=0.9, explain=True)
        memory._compute_entity_boosts_async.assert_awaited_once()
    else:
        memory._compute_entity_boosts = Mock(return_value=entities)
        result = memory._search_vector_store("Alice", filters, 3, threshold=0.9, explain=True)
        memory._compute_entity_boosts.assert_called_once()

    assert {item["id"] for item in result} == {"outside", "keyword-only", "entity-only"}
    assert all(item["memory"] != "semantic" for item in result)
    assert result[0]["score_details"]["bm25_score"] in {90.0, 100.0}
    memory.vector_store.get_by_ids.assert_called_once_with(["entity-only"], filters=filters)


def test_rrf_hydration_rejects_cross_scope_expired_and_unrequested_rows(monkeypatch):
    # The native batch reader has already rejected a cross-user row; the
    # memory layer still rejects the expired and unrequested rows defensively.
    monkeypatch.setattr("mem0.memory.main.lemmatize_for_bm25", lambda query: query)
    monkeypatch.setattr("mem0.memory.main.extract_entities", lambda query: [("PERSON", "Alice")])
    memory = Memory.__new__(Memory)
    memory.config = MemoryConfig(fusion_strategy="rrf")
    memory.embedding_model = Mock()
    memory.embedding_model.embed.return_value = [0.1, 0.2]
    memory.vector_store = Mock()
    memory.vector_store.search.return_value = []
    memory.vector_store.keyword_search.return_value = None
    memory.vector_store.get_by_ids.return_value = [
        Mock(id="valid", payload={"data": "valid", "user_id": "u1", "priority": 2}),
        Mock(id="expired", payload={"data": "expired", "user_id": "u1", "priority": 2, "expiration_date": "2000-01-01"}),
        Mock(id="not-requested", payload={"data": "extra", "user_id": "u1", "priority": 2}),
    ]
    memory._compute_entity_boosts = Mock(return_value={"valid": 0.9, "expired": 0.7})

    result = memory._search_vector_store(
        "Alice",
        {"user_id": "u1", "priority": {"gte": 1, "lte": 3}},
        5,
    )

    assert [item["id"] for item in result] == ["valid"]
    memory.vector_store.get_by_ids.assert_called_once_with(
        ["valid", "expired"],
        filters={"user_id": "u1", "priority": {"gte": 1, "lte": 3}},
    )


def test_rrf_warns_and_skips_entity_only_when_scoped_batch_is_unsupported(monkeypatch, caplog):
    monkeypatch.setattr("mem0.memory.main.lemmatize_for_bm25", lambda query: query)
    monkeypatch.setattr("mem0.memory.main.extract_entities", lambda query: [("PERSON", "Alice")])
    memory = Memory.__new__(Memory)
    memory.config = MemoryConfig(fusion_strategy="rrf")
    memory.embedding_model = Mock()
    memory.embedding_model.embed.return_value = [0.1, 0.2]
    memory.vector_store = Mock()
    memory.vector_store.search.return_value = []
    memory.vector_store.keyword_search.return_value = None
    memory.vector_store.get_by_ids.side_effect = NotImplementedError
    memory._compute_entity_boosts = Mock(return_value={"entity-only": 0.9})

    with caplog.at_level("WARNING"):
        result = memory._search_vector_store("Alice", {"user_id": "u1"}, 5)

    assert result == []
    assert any("does not support scoped batch reads" in record.message for record in caplog.records)
