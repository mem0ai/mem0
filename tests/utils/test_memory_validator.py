import pytest

from mem0.utils import MemoryValidator


class FakeMemory:
    def __init__(self, memories, search_results_by_query):
        self.memories = memories
        self.search_results_by_query = search_results_by_query
        self.get_all_calls = []
        self.search_calls = []

    def get_all(self, *, filters=None, top_k=20, **kwargs):
        self.get_all_calls.append({"filters": filters, "top_k": top_k, **kwargs})
        return {"results": self.memories}

    def search(self, query, **kwargs):
        self.search_calls.append((query, kwargs))
        return {"results": self.search_results_by_query.get(query, [])}


class FakeHostedMemory(FakeMemory):
    def get_all(self, options=None, **kwargs):
        self.get_all_calls.append(kwargs)
        return {"results": self.memories}


def test_validate_reports_retrieval_rate_and_failures():
    memory = FakeMemory(
        memories=[
            {"id": "mem-1", "memory": "Alice likes hiking."},
            {"id": "mem-2", "memory": "Bob works in Paris."},
        ],
        search_results_by_query={
            "Alice likes hiking.": [{"id": "mem-1", "memory": "Alice likes hiking."}],
            "Bob works in Paris.": [{"id": "other", "memory": "Someone lives in Paris."}],
        },
    )

    report = MemoryValidator(memory).validate(user_id="alice", sample_size=2, top_k=3)

    assert report.checked == 2
    assert report.found == 1
    assert report.retrieval_rate == 0.5
    assert len(report.failures) == 1
    assert report.failures[0].memory_id == "mem-2"
    assert report.failures[0].returned_ids == ["other"]
    assert memory.get_all_calls[0]["filters"] == {"user_id": "alice"}
    assert memory.get_all_calls[0]["top_k"] == 2
    assert memory.search_calls[0][1]["top_k"] == 3


def test_validate_supports_custom_query_builder():
    memory = FakeMemory(
        memories=[{"id": "mem-1", "memory": "Alice prefers tea.", "metadata": {"topic": "drink"}}],
        search_results_by_query={"What does Alice prefer to drink?": [{"id": "mem-1", "memory": "Alice prefers tea."}]},
    )

    report = MemoryValidator(memory).validate(
        filters={"user_id": "alice"},
        query_builder=lambda item: "What does Alice prefer to drink?",
    )

    assert report.checked == 1
    assert report.found == 1
    assert report.failures == []


def test_validate_uses_page_size_for_hosted_client_shape():
    memory = FakeHostedMemory(
        memories=[{"id": "mem-1", "memory": "Alice likes hiking."}],
        search_results_by_query={"Alice likes hiking.": [{"id": "mem-1", "memory": "Alice likes hiking."}]},
    )

    MemoryValidator(memory).validate(user_id="alice", sample_size=10)

    assert memory.get_all_calls[0]["page_size"] == 10
    assert "top_k" not in memory.get_all_calls[0]


def test_validate_requires_scope_filter():
    memory = FakeMemory(memories=[], search_results_by_query={})

    with pytest.raises(ValueError, match="filters, user_id, agent_id, or run_id is required"):
        MemoryValidator(memory).validate()


@pytest.mark.parametrize("sample_size, top_k", [(0, 5), (1, 0)])
def test_validate_rejects_invalid_limits(sample_size, top_k):
    memory = FakeMemory(memories=[], search_results_by_query={})

    with pytest.raises(ValueError):
        MemoryValidator(memory).validate(user_id="alice", sample_size=sample_size, top_k=top_k)
