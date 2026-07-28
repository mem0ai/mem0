"""The gate, tested against the classes of noise v1 actually stored.

The three verbatim strings below are real records pulled from the polluted v1
corpus -- the training-heartbeat cluster (119 near-duplicates), the chunk-
progress cluster, and the file-inventory class. If any of them stops being
dropped, the regression is the one that mattered most.
"""

from __future__ import annotations

import pytest

from mem0_agent.triggers import (
    LEVELS,
    TriggerResult,
    classify,
    repo_content_reason,
    shape_signature,
)

# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def u(text: str) -> dict:
    return {"role": "user", "content": text}


def a(text: str) -> dict:
    return {"role": "assistant", "content": text}


# --------------------------------------------------------------------------
# real-corpus hard drops
# --------------------------------------------------------------------------
TRAINING_HEARTBEAT = (
    "Task notification (task-id bukn4vw5n): v4 train metrics at epoch 0.7381/2 "
    "(37% complete) with loss 0.4727, gradient norm 0.4716, ETA 124 minutes."
)
CHUNK_PROGRESS = (
    "Progress for task bnzbd1uay: 218 of 928 chunks processed (23% complete), "
    "approximately 5,141 synthetic memories generated, 11 chunk failures, "
    "ETA about 55 minutes."
)
FILE_INVENTORY = (
    "I modified VERSION, chat.py, agent.py, types.py, chunking.py, the slack adapter, "
    "the router, the tests, and several web components in this session."
)

REAL_CORPUS_NOISE = [TRAINING_HEARTBEAT, CHUNK_PROGRESS, FILE_INVENTORY]


@pytest.mark.parametrize("text", REAL_CORPUS_NOISE)
@pytest.mark.parametrize("level", LEVELS)
def test_real_corpus_noise_is_dropped_at_every_level(text, level):
    result = classify([a(text)], level)
    assert result.action == "drop", f"{level}: {result}"
    assert result.mtype is None


@pytest.mark.parametrize(
    "text",
    [
        "Still running the backfill, no changes since the last update.",
        "Heartbeat: the job is still running, will report back in 10 minutes.",
        "Continuing to process the queue; nothing to report yet.",
        "Step 4 of 12 of the ingest pipeline, 60% complete.",
        "Elapsed: 42 minutes, ETA about 3 hours for the remaining shards.",
        "Status update: 4,102 records processed and 3 retries so far.",
    ],
)
def test_heartbeat_and_progress_phrasing_is_dropped(text):
    assert classify([a(text)], "aggressive").action == "drop"


def test_tool_only_turns_are_dropped():
    window = [
        {"role": "assistant", "content": "", "tool_calls": [{"name": "Read"}]},
        {"role": "tool", "content": '{"path": "src/app.py", "lines": 120}'},
        {"role": "tool_result", "content": "ok"},
    ]
    result = classify(window, "aggressive")
    assert result.action == "drop"
    assert result.reason == "tool_only"


def test_transcript_tool_only_flag_is_honored():
    """transcript.py hands us {role, content, tool_only}; a whole window of those is noise."""
    window = [
        {"role": "assistant", "content": "", "tool_only": True},
        {"role": "user", "content": "", "tool_only": True},
    ]
    assert classify(window, "aggressive").reason == "tool_only"


def test_subagent_transcript_is_dropped_even_when_it_reads_like_a_decision():
    window = [
        {"role": "subagent", "content": "We decided to go with Kuzu because the graph fits in memory."},
    ]
    assert classify(window, "aggressive").reason == "subagent_transcript"
    flagged = {"role": "assistant", "content": "We decided to use Kuzu because it is embedded.", "subagent": True}
    assert classify([flagged], "aggressive").action == "drop"


def test_same_shape_repeated_inside_one_window_is_dropped():
    window = [
        a("Shard 1 of the export finished cleanly with no retries at all today"),
        a("Shard 2 of the export finished cleanly with no retries at all today"),
        a("Shard 3 of the export finished cleanly with no retries at all today"),
    ]
    assert classify(window, "aggressive").action == "drop"


def test_repeat_of_a_recently_seen_shape_is_dropped():
    window = [u("Let's go with Postgres instead of DynamoDB because the access patterns are relational.")]
    first = classify(window, "balanced")
    assert first.action == "flag"

    again = classify(window, "balanced", recent_shapes=[shape_signature(window)])
    assert again.action == "drop"
    assert again.reason == "repeated_shape"


def test_shape_signature_ignores_ids_counts_and_percentages():
    one = [a("Training run alpha: 12 of 40 steps done, 30% complete, ETA 9 minutes.")]
    two = [a("Training run alpha: 31 of 40 steps done, 77% complete, ETA 4 minutes.")]
    other = [a("The release branch is cut and the changelog has been written.")]
    assert shape_signature(one) == shape_signature(two)
    assert shape_signature(one) != shape_signature(other)


# --------------------------------------------------------------------------
# repo content -- client-side omission is the only enforcement
# --------------------------------------------------------------------------
CLAUDE_MD_PASTE = """Here are the contents of our CLAUDE.md so you have the project rules:

# AGENTS.md

## Repository Structure

This is a polyglot monorepo containing Python and TypeScript packages.

## Coding Standards

- Python source files use snake_case.py
- Ruff is the single linting and formatting tool
"""

MARKDOWN_DUMP = """# Mem0

## Installation

pip install mem0ai

## Quickstart

from mem0 import Memory

## License

Apache-2.0
"""

CONFIG_PASTE = """This is our pyproject.toml:

```toml
[tool.ruff]
line-length = 120
target-version = "py310"
```
"""


@pytest.mark.parametrize("text", [CLAUDE_MD_PASTE, MARKDOWN_DUMP, CONFIG_PASTE])
@pytest.mark.parametrize("level", LEVELS)
def test_repo_content_is_always_dropped(text, level):
    result = classify([u(text)], level)
    assert result.action == "drop", result
    assert result.reason.startswith("repo_content:")
    assert repo_content_reason([u(text)]) is not None


def test_repo_content_detector_leaves_genuine_prose_alone():
    genuine = [
        u("Always name migration files with a UTC timestamp prefix - that's the rule here."),
        u("Remember this: I want the linter run before you tell me a task is done."),
        a("The root cause was that latest_only defaults to false on that endpoint."),
    ]
    for turn in genuine:
        assert repo_content_reason([turn]) is None


def test_repo_content_beats_a_convention_sounding_paste():
    """A pasted rule reads exactly like a stated rule; only the paste is dropped."""
    pasted = u("Here are the contents of our CLAUDE.md:\n\n# Rules\n\nTests must be added for every fix.")
    stated = u("Tests must be added for every fix - that's the rule here, even for one-liners.")
    assert classify([pasted], "balanced").action == "drop"
    assert classify([stated], "balanced").action == "flag"


# --------------------------------------------------------------------------
# flag rules and their types
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "window,level,mtype",
    [
        (
            [u("Remember this: I always want the linter run before you tell me a task is done.")],
            "conservative",
            "preference",
        ),
        (
            [u("Don't forget that I review diffs top-down, so keep the summary at the end.")],
            "conservative",
            "preference",
        ),
        (
            [a("I'll add a helper for that."), u("No, actually, stop doing that - inline it instead.")],
            "conservative",
            "preference",
        ),
        (
            [u("I told you already: don't run the full suite on every save.")],
            "conservative",
            "preference",
        ),
        (
            [
                a("Postgres or DynamoDB for the event log?"),
                u("Let's go with Postgres because our access patterns are relational."),
            ],
            "balanced",
            "decision",
        ),
        (
            [a("The retry loop silently swallowed the 429, so the root cause was the missing backoff.")],
            "balanced",
            "insight",
        ),
        (
            [u("Always name migration files with a UTC timestamp prefix - that's the rule here.")],
            "balanced",
            "convention",
        ),
        (
            [
                u(
                    "1. bump the version in pyproject\n"
                    "2. tag the commit\n"
                    "3. dispatch the publish workflow\n"
                    "I verified those steps end to end on the last release."
                )
            ],
            "aggressive",
            "runbook",
        ),
        (
            [
                u("Finish the pgvector migration and run the suite."),
                a("Schema migrated and the embedding column is backfilled."),
                a("All tests are passing now, so the migration is complete."),
            ],
            "aggressive",
            "insight",
        ),
    ],
)
def test_genuine_windows_are_flagged_with_the_right_type(window, level, mtype):
    result = classify(window, level)
    assert result.action == "flag", result
    assert result.mtype == mtype, result


# --- stated standing preferences: the highest-value thing this plugin captures ---
STANDING_PREFERENCES = [
    # Found by integration testing: a closed verb list after "stop" missed this entirely.
    "Stop dumping the whole diff at me every time. Show me the failing test output first, "
    "then the fix. That's how I want it from now on.",
    "stop showing me the full output",
    "I prefer rebase over merge for this repo.",
    "From now on, run the type checker before you hand a task back.",
    "I'd rather you asked before touching the lockfile.",
    "Please always put the summary at the end, going forward.",
]


@pytest.mark.parametrize("text", STANDING_PREFERENCES)
@pytest.mark.parametrize("level", LEVELS)
def test_standing_preferences_are_flagged_at_every_level(text, level):
    result = classify([u(text)], level)
    assert result.action == "flag", result
    assert result.mtype == "preference", result


@pytest.mark.parametrize("text", STANDING_PREFERENCES)
def test_standing_preference_phrasing_from_the_assistant_is_not_a_preference(text):
    """scope=user is load-bearing: the assistant's own narration is not the user's rule."""
    assert classify([a(text)], "balanced").mtype != "preference"


@pytest.mark.parametrize("text", REAL_CORPUS_NOISE)
@pytest.mark.parametrize("level", LEVELS)
def test_noise_still_drops_after_widening_the_preference_rules(text, level):
    """Hard drops run before every flag rule, including from a user turn."""
    assert classify([u(text)], level).action == "drop"
    assert classify([u(text + " Do this every time, from now on.")], level).action == "drop"


def test_one_off_instructions_are_not_preferences():
    """'skip tests for now' is a task instruction; only standing rules get stored."""
    for text in (
        "Skip the tests for now and just get the build green.",
        "You do it this time, I'm out of patience.",
        "Just run it yourself and paste what you get.",
    ):
        assert classify([u(text)], "balanced").action == "skip", text


def test_remember_intent_takes_the_type_from_the_phrasing():
    window = [u("Remember that we decided to use Kuzu for the graph store because it is embedded.")]
    result = classify(window, "conservative")
    assert result == TriggerResult("flag", "decision", "remember_intent")


def test_assistant_chatter_is_not_a_user_preference():
    """Attribution: the assistant saying 'remember this' must not create a preference."""
    window = [a("Remember this: I always run the linter before finishing a task.")]
    assert classify(window, "conservative").action != "flag"


# --------------------------------------------------------------------------
# level gating
# --------------------------------------------------------------------------
DECISION_WINDOW = [
    a("Should the event log go in Postgres or DynamoDB?"),
    u("Let's go with Postgres because our access patterns are relational."),
]

RUNBOOK_WINDOW = [
    u(
        "1. bump the version in pyproject\n"
        "2. tag the commit\n"
        "3. dispatch the publish workflow\n"
        "I verified those steps end to end on the last release."
    )
]


def test_decision_is_gated_to_balanced_and_up():
    assert classify(DECISION_WINDOW, "conservative").action == "skip"
    assert classify(DECISION_WINDOW, "balanced") == TriggerResult("flag", "decision", "decision_language")
    assert classify(DECISION_WINDOW, "aggressive").mtype == "decision"


def test_runbook_is_gated_to_aggressive_only():
    assert classify(RUNBOOK_WINDOW, "conservative").action == "skip"
    assert classify(RUNBOOK_WINDOW, "balanced").action == "skip"
    assert classify(RUNBOOK_WINDOW, "aggressive").mtype == "runbook"


def test_explicit_intent_survives_the_most_conservative_level():
    window = [u("Remember this: I always want the linter run before you tell me a task is done.")]
    assert classify(window, "conservative").action == "flag"


def test_unknown_level_falls_back_to_balanced():
    assert classify(DECISION_WINDOW, "nonsense").mtype == "decision"


# --------------------------------------------------------------------------
# nothing-to-store
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "window",
    [
        [],
        [u("Now look at the retry helper in the client and tell me what it does.")],
        [a("Sure, I'll take a look at that file and report what I find.")],
    ],
)
def test_ordinary_working_turns_are_skipped(window):
    assert classify(window, "balanced").action == "skip"
