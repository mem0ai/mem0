# Mem0 Evaluation Toolkit

Deterministic eval framework for measuring memory quality in agent workflows.

## Overview

When agents use Mem0 as a memory layer, four failure modes can silently degrade quality:

1. **Forgetting**: Old memories aren't deprioritized when they should be
2. **Overwrite behavior**: Updates don't fully supersede previous facts
3. **Temporal relevance**: Stale facts rank higher than recent ones
4. **Conflict resolution**: Wrong fact wins when contradictions exist

The `mem0.evals` module provides a scenario-based evaluation API to measure and debug these failures.

## Quick Start

```python
from mem0 import Memory
from mem0.evals import MemoryEvent, MemoryScenario, evaluate_memory

# Define a scenario that tests temporal relevance
scenario = MemoryScenario(
    name="job_update",
    user_id="alice",
    events=[
        MemoryEvent(action="add", text="I work at Google.", memory_id="job_1"),
        MemoryEvent(action="add", text="I work at OpenAI.", memory_id="job_2"),
        MemoryEvent(action="query", text="Where do I work?"),
    ],
    expected="I work at OpenAI",  # Newer fact should win
    stale=["I work at Google"],   # Older fact should be deprioritized
)

# Run the scenario against your Memory client
client = Memory()
result = evaluate_memory(client, scenario)

print(f"Recall: {result.memory_recall_rate:.2f}")  # Did we retrieve the right fact?
print(f"Staleness: {result.staleness_score:.2f}")  # How many stale facts surfaced?
print(f"Conflict resolution: {result.conflict_resolution_acc:.2f}")  # Did newer beat older?
```

## Core Metrics

| Metric | Description |
|--------|-------------|
| `memory_recall_rate` | Did the expected memory get retrieved? (0.0 or 1.0) |
| `staleness_score` | Fraction of retrieved memories that are stale (lower is better) |
| `conflict_resolution_acc` | When conflicting facts exist, does the right one rank highest? |
| `update_propagation_rate` | After an update, is the old version fully replaced? |

## Scenario API

### Events

```python
# Add a memory
MemoryEvent(action="add", text="My cat's name is Whiskers.", memory_id="cat_1")

# Update an existing memory (requires memory_id)
MemoryEvent(action="update", memory_id="cat_1", text="My cat's name is Shadow.")

# Query the memory layer
MemoryEvent(action="query", text="What is my cat's name?")
```

### Scenarios

```python
MemoryScenario(
    name="unique_test_name",
    user_id="test_user",
    events=[...],               # List of MemoryEvents (must include at least one query)
    expected="correct answer",  # Text that should be in the top-ranked memory
    stale=[...],                # List of texts that should NOT rank high
    top_k=5,                    # Number of memories to retrieve (default: 5)
    match_threshold=0.72,       # Token F1 threshold for fuzzy matching (default: 0.72)
)
```

## Common Patterns

### Test Forgetting

Validate that old preferences are deprioritized after an update.

```python
MemoryScenario(
    name="preference_update",
    user_id="user_1",
    events=[
        MemoryEvent(action="add", text="I prefer dark mode.", memory_id="pref_1"),
        MemoryEvent(action="update", memory_id="pref_1", text="I prefer light mode."),
        MemoryEvent(action="query", text="What is my UI preference?"),
    ],
    expected="I prefer light mode",
    stale=["I prefer dark mode"],
)
```

### Test Conflict Resolution

Ensure that when two conflicting facts exist, the newer one wins.

```python
MemoryScenario(
    name="location_conflict",
    user_id="user_2",
    events=[
        MemoryEvent(action="add", text="I live in New York."),
        MemoryEvent(action="add", text="I live in San Francisco."),
        MemoryEvent(action="query", text="Where do I live?"),
    ],
    expected="I live in San Francisco",
    stale=["I live in New York"],
)
```

### Test Temporal Relevance

Validate that recent additions rank higher than old ones.

```python
MemoryScenario(
    name="job_history",
    user_id="user_3",
    events=[
        MemoryEvent(action="add", text="I worked at Startup A in 2020."),
        MemoryEvent(action="add", text="I worked at Big Tech in 2023."),
        MemoryEvent(action="add", text="I work at AI Lab now."),
        MemoryEvent(action="query", text="Where do I work?"),
    ],
    expected="I work at AI Lab now",
    stale=["I worked at Startup A", "I worked at Big Tech"],
)
```

## Running Tests

The `tests/test_evals/` directory includes regression tests for common failure modes:

```bash
pytest tests/test_evals/test_memory_scenarios.py -v
```

## API Compatibility

The evaluator is **API-agnostic**. It works with:
- OSS `Memory` class
- Hosted `MemoryClient`
- Any test double that implements `add(messages, user_id)`, `update(memory_id, text)`, and `search(query, top_k, filters)`

## Related Issues

- [#5235](https://github.com/mem0ai/mem0/issues/5235) — Feature request for memory eval toolkit
- [#5307](https://github.com/mem0ai/mem0/pull/5307) — Core eval framework implementation

## License

Same as Mem0 (Apache-2.0)
