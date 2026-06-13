from mem0.evals.memory import MemoryEvent, MemoryScenario, RetrievedMemory, evaluate_memory, score_retrieval


class FakeMemoryClient:
    def __init__(self, *, additive_updates=False):
        self.additive_updates = additive_updates
        self.memories = {}
        self.next_id = 1

    def add(self, messages, **kwargs):
        memory_id = str(self.next_id)
        self.next_id += 1
        self.memories[memory_id] = messages[0]["content"]
        return {"results": [{"id": memory_id, "memory": self.memories[memory_id]}]}

    def update(self, memory_id, text):
        if self.additive_updates:
            new_memory_id = str(self.next_id)
            self.next_id += 1
            self.memories[new_memory_id] = text
            return {"results": [{"id": new_memory_id, "memory": text}]}

        self.memories[memory_id] = text
        return {"results": [{"id": memory_id, "memory": text}]}

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
    assert result.retrieved_memory_ids == ["old", "new"]
    assert result.failure_modes == ["stale_memory_retrieved", "stale_memory_ranked_above_expected"]


def test_evaluate_memory_scores_updated_fact_over_stale_fact():
    scenario = MemoryScenario(
        name="preference-update",
        user_id="user-123",
        expected_memory_id="preference",
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
    assert result.expected_memory_ids == ["1"]
    assert result.memory_recall_rate == 1.0
    assert result.staleness_score == 0.0
    assert result.conflict_resolution_acc == 1.0
    assert result.update_propagation_rate == 1.0
    assert result.failure_modes == []
    assert [step.action for step in result.trace] == ["add", "update", "query"]
    assert result.trace[0].response_summary["memory_ids"] == ["1"]
    assert result.to_dict()["trace"][2]["retrieved"][0]["memory_id"] == "1"


def test_normalizes_payload_data_search_results():
    result = score_retrieval(
        scenario_name="payload-shape",
        query="Which plan?",
        retrieved=[RetrievedMemory(text="The user is on the enterprise plan.", rank=1)],
        expected="user is on the enterprise plan",
    )

    assert result.expected_match_score == 1.0
    assert result.memory_recall_rate == 1.0


def test_scores_expected_and_stale_memory_ids_when_text_is_rewritten():
    result = score_retrieval(
        scenario_name="rewritten-fact",
        query="Which timezone should the scheduler use?",
        retrieved=[
            RetrievedMemory(text="The scheduler should use Pacific Time.", memory_id="new", rank=1),
            RetrievedMemory(text="The scheduler should use Eastern Time.", memory_id="old", rank=2),
        ],
        expected="Use the user's latest timezone preference.",
        expected_memory_ids=["new"],
        stale=["The scheduler should use Eastern Time."],
        stale_memory_ids=["old"],
    )

    assert result.expected_best_match.memory_id == "new"
    assert result.expected_match_score < result.memory_recall_rate
    assert result.stale_matches[0].memory_id == "old"
    assert result.conflict_resolution_acc == 1.0
    assert result.update_propagation_rate == 0.0
    assert result.failure_modes == ["stale_memory_retrieved"]


def test_report_separates_write_trace_from_bad_later_recall():
    scenario = MemoryScenario(
        name="additive-update-stale-rank",
        user_id="user-123",
        expected_memory_id="preference",
        stale_memory_ids=["preference"],
        events=[
            MemoryEvent(action="add", text="Ritwij wants deployment alerts by email.", memory_id="preference"),
            MemoryEvent(action="update", text="Ritwij wants deployment alerts in Slack.", memory_id="preference"),
            MemoryEvent(action="query", text="Where should deployment alerts go?"),
        ],
        expected="Ritwij wants deployment alerts in Slack.",
        stale=["Ritwij wants deployment alerts by email."],
    )

    result = evaluate_memory(FakeMemoryClient(additive_updates=True), scenario)

    assert result.trace[0].resolved_memory_id == "1"
    assert result.trace[1].resolved_memory_id == "1"
    assert result.retrieved_memory_ids == ["2", "1"]
    assert result.expected_best_match.memory_id == "2"
    assert result.stale_matches[0].memory_id == "1"
    assert result.failure_modes == ["stale_memory_retrieved"]
    report = result.to_dict()
    assert report["metrics"]["memory_recall_rate"] == 1.0
    assert report["trace"][0]["response_summary"]["memory_ids"] == ["1"]
