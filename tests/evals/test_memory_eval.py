from mem0.evals.memory import MemoryEvent, MemoryScenario, RetrievedMemory, evaluate_memory, score_retrieval


class FakeMemoryClient:
    def __init__(self):
        self.memories = {}
        self.next_id = 1

    def add(self, messages, **kwargs):
        memory_id = str(self.next_id)
        self.next_id += 1
        self.memories[memory_id] = messages[0]["content"]
        return {"results": [{"id": memory_id, "memory": self.memories[memory_id]}]}

    def update(self, memory_id, text):
        self.memories[memory_id] = text

    def search(self, query, **kwargs):
        return {
            "results": [
                {"id": memory_id, "memory": memory}
                for memory_id, memory in sorted(self.memories.items(), key=lambda item: item[0], reverse=True)
            ]
        }


def test_score_retrieval_detects_stale_memory_above_expected():
    result = score_retrieval(
        scenario_name="timezone-conflict",
        query="When should I call Alex?",
        retrieved=[
            RetrievedMemory(text="Alex prefers morning calls.", memory_id="old", rank=1),
            RetrievedMemory(text="Alex now prefers evening calls.", memory_id="new", rank=2),
        ],
        expected="Alex now prefers evening calls.",
        stale=["Alex prefers morning calls."],
    )

    assert result.memory_recall_rate == 1.0
    assert result.staleness_score == 0.5
    assert result.conflict_resolution_acc == 0.0
    assert result.update_propagation_rate == 0.0


def test_evaluate_memory_scores_updated_fact_over_stale_fact():
    scenario = MemoryScenario(
        name="preference-update",
        user_id="user-123",
        events=[
            MemoryEvent(action="add", text="Ritwij prefers email updates in the morning.", memory_id="preference"),
            MemoryEvent(
                action="update", text="Ritwij now prefers email updates in the evening.", memory_id="preference"
            ),
            MemoryEvent(action="query", text="When should I send Ritwij updates?"),
        ],
        expected="Ritwij now prefers email updates in the evening.",
        stale=["Ritwij prefers email updates in the morning."],
    )

    result = evaluate_memory(FakeMemoryClient(), scenario)

    assert result.expected_best_match.memory_id == "1"
    assert result.memory_recall_rate == 1.0
    assert result.staleness_score == 0.0
    assert result.conflict_resolution_acc == 1.0
    assert result.update_propagation_rate == 1.0


def test_normalizes_payload_data_search_results():
    result = score_retrieval(
        scenario_name="payload-shape",
        query="Which plan?",
        retrieved=[RetrievedMemory(text="The user is on the enterprise plan.", rank=1)],
        expected="user is on the enterprise plan",
    )

    assert result.expected_match_score == 1.0
    assert result.memory_recall_rate == 1.0
