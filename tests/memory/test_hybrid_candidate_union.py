from collections import UserDict
from unittest.mock import MagicMock, patch

import pytest

from mem0 import AsyncMemory, Memory


class SearchResult:
    def __init__(self, memory_id, data, score, **payload):
        self.id = memory_id
        self.payload = {"data": data, "user_id": "user-1", **payload}
        self.score = score


@pytest.fixture(autouse=True)
def patch_query_preprocessing():
    with (
        patch("mem0.memory.main.extract_entities", return_value=[]),
        patch("mem0.memory.main.lemmatize_for_bm25", return_value="zxq 914"),
    ):
        yield


def build_memory(memory_class, semantic_results, keyword_results):
    memory = memory_class.__new__(memory_class)
    memory.embedding_model = MagicMock()
    memory.embedding_model.embed.return_value = [0.1, 0.2, 0.3]
    memory.vector_store = MagicMock()
    memory.vector_store.search.return_value = semantic_results
    memory.vector_store.keyword_search.return_value = keyword_results
    return memory


def test_search_returns_strong_keyword_only_candidate():
    memory = build_memory(
        Memory,
        [SearchResult("semantic-only", "General product documentation", 0.8)],
        [SearchResult("keyword-only", "Replacement procedure for part ZXQ-914", 20.0)],
    )

    results = memory._search_vector_store("ZXQ-914", {"user_id": "user-1"}, limit=2)

    assert [result["id"] for result in results] == ["keyword-only", "semantic-only"]
    assert all("_keyword_only" not in result for result in results)


@pytest.mark.asyncio
async def test_async_search_returns_strong_keyword_only_candidate():
    memory = build_memory(
        AsyncMemory,
        [SearchResult("semantic-only", "General product documentation", 0.8)],
        [SearchResult("keyword-only", "Replacement procedure for part ZXQ-914", 20.0)],
    )

    results = await memory._search_vector_store("ZXQ-914", {"user_id": "user-1"}, limit=2)

    assert [result["id"] for result in results] == ["keyword-only", "semantic-only"]


def test_semantic_only_results_keep_scores_and_order():
    memory = build_memory(
        Memory,
        [
            SearchResult("first", "First semantic result", 0.9),
            SearchResult("second", "Second semantic result", 0.4),
        ],
        [],
    )

    results = memory._search_vector_store("semantic query", {"user_id": "user-1"}, limit=2)

    assert [result["id"] for result in results] == ["first", "second"]
    assert [result["score"] for result in results] == pytest.approx([0.9, 0.4])


def test_duplicate_semantic_id_keeps_first_result():
    memory = build_memory(
        Memory,
        [
            SearchResult("shared", "First semantic payload", 0.9),
            SearchResult("shared", "Duplicate semantic payload", 0.4),
        ],
        [],
    )

    results = memory._search_vector_store("semantic query", {"user_id": "user-1"}, limit=2)

    assert len(results) == 1
    assert results[0]["memory"] == "First semantic payload"
    assert results[0]["score"] == pytest.approx(0.9)


def test_overlapping_candidate_is_deduplicated_and_keeps_semantic_payload():
    memory = build_memory(
        Memory,
        [SearchResult("shared", "Semantic payload", 0.8)],
        [SearchResult("shared", "Keyword payload", 20.0)],
    )

    results = memory._search_vector_store(
        "ZXQ-914",
        {"user_id": "user-1"},
        limit=2,
        explain=True,
    )

    assert len(results) == 1
    assert results[0]["memory"] == "Semantic payload"
    assert results[0]["score_details"]["semantic_score"] == 0.8
    assert results[0]["score_details"]["bm25_score"] > 0.99


def test_expired_keyword_only_candidate_respects_show_expired():
    keyword_result = SearchResult(
        "expired",
        "Old procedure for ZXQ-914",
        20.0,
        expiration_date="2000-01-01",
    )
    memory = build_memory(Memory, [], [keyword_result])

    hidden = memory._search_vector_store("ZXQ-914", {"user_id": "user-1"}, limit=2)
    visible = memory._search_vector_store(
        "ZXQ-914",
        {"user_id": "user-1"},
        limit=2,
        show_expired=True,
    )

    assert hidden == []
    assert [result["id"] for result in visible] == ["expired"]


def test_expired_semantic_candidate_is_not_readmitted_by_sparse_overlap():
    memory = build_memory(
        Memory,
        [
            SearchResult(
                "expired-overlap",
                "Expired semantic payload",
                0.8,
                expiration_date="2000-01-01",
            )
        ],
        [SearchResult("expired-overlap", "Sparse payload without expiration", 20.0)],
    )

    results = memory._search_vector_store("ZXQ-914", {"user_id": "user-1"}, limit=2)

    assert results == []


def test_keyword_only_mapping_result_is_supported():
    memory = build_memory(
        Memory,
        [],
        [
            UserDict(
                {
                    "id": "mapping-result",
                    "payload": {"data": "Procedure for ZXQ-914", "user_id": "user-1"},
                    "score": 20.0,
                }
            )
        ],
    )

    results = memory._search_vector_store("ZXQ-914", {"user_id": "user-1"}, limit=1)

    assert [result["id"] for result in results] == ["mapping-result"]


def test_mapping_fields_take_precedence_over_attributes():
    keyword_result = UserDict(
        {
            "id": "mapping-result",
            "payload": {"data": "Procedure for ZXQ-914", "user_id": "user-1"},
            "score": 20.0,
        }
    )
    keyword_result.id = "attribute-result"
    keyword_result.score = 20.0
    memory = build_memory(Memory, [], [keyword_result])

    results = memory._search_vector_store("ZXQ-914", {"user_id": "user-1"}, limit=1)

    assert [result["id"] for result in results] == ["mapping-result"]


def test_idless_keyword_result_does_not_rescale_semantic_candidates():
    memory = build_memory(
        Memory,
        [SearchResult("semantic-only", "Semantic payload", 0.8)],
        [UserDict({"payload": {"data": "ID-less sparse payload"}, "score": 20.0})],
    )

    results = memory._search_vector_store("ZXQ-914", {"user_id": "user-1"}, limit=1)

    assert [result["id"] for result in results] == ["semantic-only"]
    assert results[0]["score"] == pytest.approx(0.8)


def test_non_positive_keyword_score_does_not_create_candidate():
    memory = build_memory(
        Memory,
        [],
        [SearchResult("no-match", "Unscored keyword result", 0.0)],
    )

    results = memory._search_vector_store("ZXQ-914", {"user_id": "user-1"}, limit=1)

    assert results == []


def test_search_passes_identical_filters_to_dense_and_sparse_retrieval():
    memory = build_memory(Memory, [], [])
    filters = {"user_id": "user-1", "category": "manual"}

    memory._search_vector_store("ZXQ-914", filters, limit=2)

    memory.vector_store.search.assert_called_once_with(
        query="ZXQ-914",
        vectors=[0.1, 0.2, 0.3],
        top_k=60,
        filters=filters,
    )
    memory.vector_store.keyword_search.assert_called_once_with(
        query="zxq 914",
        top_k=60,
        filters=filters,
    )


def test_tied_keyword_only_candidates_keep_provider_order():
    memory = build_memory(
        Memory,
        [],
        [
            SearchResult("first", "First ZXQ-914 procedure", 20.0),
            SearchResult("second", "Second ZXQ-914 procedure", 20.0),
        ],
    )

    results = memory._search_vector_store("ZXQ-914", {"user_id": "user-1"}, limit=2)

    assert [result["id"] for result in results] == ["first", "second"]
