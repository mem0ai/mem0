import inspect
from unittest.mock import AsyncMock, MagicMock

import pytest

from mem0.memory import main as memory_main
from mem0.memory.main import AsyncMemory, Memory

KINDS = ["sync", "async"]


def count_chars(text):
    return len(text)


def make_results():
    return [
        {"id": "m1", "memory": "likes tea", "score": 0.9, "metadata": {"source": "chat"}},
        {"id": "m2", "memory": "x" * 50, "score": 0.8},
        {"id": "m3", "memory": "dislikes coffee", "score": 0.7},
        {"id": "m4", "memory": "vegan", "score": 0.6},
    ]


def make_memory(kind, results, reranker=None):
    cls = Memory if kind == "sync" else AsyncMemory
    memory = cls.__new__(cls)
    memory.api_version = "v1.1"
    memory.reranker = reranker
    mock_cls = MagicMock if kind == "sync" else AsyncMock
    memory._search_vector_store = mock_cls(return_value=results)
    return memory


async def run_search(memory, **kwargs):
    kwargs.setdefault("filters", {"user_id": "u1"})
    result = type(memory).search(memory, "food preferences", **kwargs)
    if inspect.isawaitable(result):
        result = await result
    return result


@pytest.fixture(autouse=True)
def quiet_search(monkeypatch):
    monkeypatch.setattr(memory_main, "capture_event", MagicMock())
    for name in (
        "display_first_run_notice",
        "display_performance_slow_query_notice",
        "display_scale_threshold_notice",
        "display_temporal_usage_notice",
    ):
        monkeypatch.setattr(memory_main, name, MagicMock())
        monkeypatch.setattr(memory_main, f"{name}_async", AsyncMock())


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", KINDS)
async def test_search_without_token_budget_is_unchanged(kind):
    results = make_results()
    memory = make_memory(kind, results)
    counter = MagicMock(return_value=0)

    assert await run_search(memory) == {"results": make_results()}
    # A counter on its own does nothing: the budget is what turns the feature on.
    assert await run_search(memory, token_counter=counter) == {"results": make_results()}
    counter.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", KINDS)
async def test_zero_token_budget_returns_no_memories(kind):
    memory = make_memory(kind, make_results())

    result = await run_search(memory, token_budget=0, token_counter=count_chars)

    assert result == {"results": []}


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("budget", [-1, 1.5, "10", True])
async def test_invalid_token_budget_is_rejected_before_searching(kind, budget):
    memory = make_memory(kind, make_results())

    with pytest.raises(ValueError, match="token_budget"):
        await run_search(memory, token_budget=budget, token_counter=count_chars)
    memory._search_vector_store.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("counter", [None, "len"])
async def test_token_budget_requires_a_callable_token_counter(kind, counter):
    memory = make_memory(kind, make_results())

    with pytest.raises(ValueError, match="token_counter"):
        await run_search(memory, token_budget=100, token_counter=counter)
    memory._search_vector_store.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", KINDS)
async def test_oversized_memory_is_skipped_and_later_memories_still_fit(kind):
    memory = make_memory(kind, make_results())

    # "likes tea" (9) fits. The 50-char memory would make 60, so it is skipped.
    # "likes tea\ndislikes coffee" is 25 and fits. Adding "\nvegan" makes 31: over by the separator alone.
    result = await run_search(memory, token_budget=30, token_counter=count_chars)

    assert [m["id"] for m in result["results"]] == ["m1", "m3"]


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", KINDS)
async def test_token_counter_sees_only_memory_text_joined_by_the_separator(kind):
    memory = make_memory(kind, make_results())
    seen = []

    def counter(text):
        seen.append(text)
        return len(text)

    await run_search(memory, token_budget=30, token_counter=counter)

    sep = memory_main.TOKEN_BUDGET_SEPARATOR
    assert sep == "\n"
    assert seen == [
        "likes tea",
        "likes tea" + sep + "x" * 50,
        "likes tea" + sep + "dislikes coffee",
        "likes tea" + sep + "dislikes coffee" + sep + "vegan",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", KINDS)
async def test_kept_memories_are_unmodified_and_keep_their_order_and_scores(kind):
    results = make_results()
    memory = make_memory(kind, results)

    result = await run_search(memory, token_budget=1000, token_counter=count_chars)

    assert result["results"] == make_results()
    assert all(kept is original for kept, original in zip(result["results"], results))


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", KINDS)
async def test_memory_that_fits_exactly_is_kept(kind):
    memory = make_memory(kind, make_results())

    result = await run_search(memory, token_budget=9, token_counter=count_chars)

    assert [m["id"] for m in result["results"]] == ["m1"]


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", KINDS)
async def test_single_memory_over_budget_returns_no_memories(kind):
    memory = make_memory(kind, [{"id": "m1", "memory": "a long memory", "score": 0.9}])

    result = await run_search(memory, token_budget=5, token_counter=count_chars)

    assert result == {"results": []}


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", KINDS)
async def test_token_budget_follows_the_reranked_order(kind):
    results = make_results()
    reranker = MagicMock()
    reranker.rerank.return_value = list(reversed(results))
    memory = make_memory(kind, results, reranker=reranker)

    result = await run_search(memory, rerank=True, token_budget=21, token_counter=count_chars)

    # Reranked order is m4, m3, m2, m1: "vegan\ndislikes coffee" is 21 and fills the budget.
    assert [m["id"] for m in result["results"]] == ["m4", "m3"]
    reranker.rerank.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("bad_count", [-1, "3", 2.5, None])
async def test_token_counter_must_return_a_non_negative_integer(kind, bad_count):
    memory = make_memory(kind, make_results())

    with pytest.raises(ValueError, match="token_counter"):
        await run_search(memory, token_budget=10, token_counter=lambda text: bad_count)
