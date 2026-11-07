"""Real-store regression for RRF auxiliary candidate scope and expiration."""
import uuid
from types import SimpleNamespace
from unittest.mock import Mock

from mem0.configs.base import MemoryConfig
from mem0.memory.main import Memory
from mem0.vector_stores.qdrant import Qdrant


def test_union_rrf_uses_real_scoped_qdrant_for_entity_payloads(tmp_path, monkeypatch):
    monkeypatch.setattr("mem0.memory.main.lemmatize_for_bm25", lambda query: query)
    monkeypatch.setattr("mem0.memory.main.extract_entities", lambda query: [("PERSON", "Alice")])
    store = Qdrant(collection_name="union_scope", embedding_model_dims=2, path=str(tmp_path / "qdrant"))
    ids = {name: str(uuid.uuid4()) for name in ("keyword", "entity", "foreign", "denied", "expired")}
    semantic_ids = [str(uuid.uuid4()) for _ in range(60)]
    all_ids = semantic_ids + list(ids.values())
    payloads = [{"data": key, "user_id": "alice", "kind": "fact", "rating": 5} for key in all_ids]
    payloads[-3]["user_id"] = "bob"
    payloads[-2]["rating"] = 99
    payloads[-1]["expiration_date"] = "2000-01-01"
    store.insert(vectors=[[1.0, 0.0]] * 60 + [[0.0, 1.0]] * 5, ids=all_ids, payloads=payloads)
    native_get = store.get_by_ids
    batch_get = Mock(wraps=native_get)
    store.get_by_ids = batch_get

    def keyword_search(query, top_k, filters):
        point = native_get([ids["keyword"]], filters=filters)[0]
        return [SimpleNamespace(id=point.id, score=10.0, payload=point.payload)]

    store.keyword_search = keyword_search
    memory = Memory.__new__(Memory)
    memory.config = MemoryConfig(fusion_strategy="rrf")
    memory.vector_store = store
    memory.embedding_model = Mock()
    memory.embedding_model.embed.return_value = [1.0, 0.0]
    memory._compute_entity_boosts = Mock(return_value={
        ids["foreign"]: 1.0, ids["denied"]: 0.95, ids["expired"]: 0.9,
        ids["entity"]: 0.8, ids["keyword"]: 0.7,
    })
    filters = {"user_id": "alice", "kind": "fact", "rating": {"gte": 3, "lte": 8}}
    try:
        result = memory._search_vector_store("question", filters, 2, explain=True)
        assert [row["id"] for row in result] == [ids["keyword"], ids["entity"]], {
            "ids": ids, "results": [(row["id"], row["score_details"]) for row in result],
            "hydrated": [(row.id, row.payload) for row in native_get(list(ids.values()), filters=filters)],
        }
        assert all(row["score_details"]["semantic_rank"] is None for row in result)
        assert batch_get.call_count == 1
        assert batch_get.call_args.kwargs["filters"] == filters
        assert set(batch_get.call_args.args[0]) == {ids[key] for key in ("entity", "foreign", "denied", "expired")}
        memory.config.fusion_strategy = "additive"
        original = memory._search_vector_store("question", filters, 2)
        assert all(row["id"] in semantic_ids for row in original)
        assert batch_get.call_count == 1
    finally:
        store.client.close()
