---
name: mem0-mcp
description: >
  Mem0 memory protocol for agents using the mem0 MCP tools (Claude Code, Cursor,
  Codex, and any other MCP-aware runtime). Decide deliberately when memory context
  would help, run targeted searches with metadata filters when it would, and store
  key learnings as work completes. Use the mem0 MCP tools (add_memory,
  search_memories, get_memories, etc.) for all memory operations.
---

# Mem0 MCP Memory Protocol

You have access to persistent memory via the mem0 MCP tools. Follow this protocol to maintain context across sessions.

## On every new task

Decide whether persistent memory context would improve your response, then act accordingly. Don't search by default — search deliberately.

## Project scoping

Every memory operation MUST be scoped to the current project using `app_id` (entity-scoped memory):

- **On `add_memory`:** Always pass `app_id=<active_project_id>` as a **top-level parameter** (not in metadata).
- **On `search_memories`:** Always include `{"app_id": "<your_project_id>"}` in the AND filter.

Full filter template:
```python
filters={"AND": [
    {"user_id": "<your_user_id>"},
    {"app_id": "<your_project_id>"},
    {"metadata": {"type": "decision"}}
]}
```

### Decide: search or skip?

**Search WHEN** the user:
- references past work, decisions, or things "we" built
- asks "how should we...", "best way to...", or any decision-style question
- hits an error, bug, or asks for debugging help
- requests work that touches their stack, tools, conventions, or preferences
- starts a non-trivial task in a known project

**Skip WHEN:**
- the prompt is an acknowledgement or continuation ("ok", "thanks", "continue")
- the user is *stating* new info — that's a write trigger (`add_memory`), not a search
- it's a pure syntax / factual question answerable from general knowledge
- you already searched this scope earlier in the turn

Empty results are normal. Proceed without context — they don't mean the system is broken.

### How to search well

When you do search, run **2–4 parallel** `search_memories` calls at different angles instead of one query echoing the user's prompt.

**Query phrasing:**
- Use **nouns**, not sentences. `"auth module decisions"` beats `"what did we decide about auth"`.
- Strip conversational filler. *"remember when we picked Postgres?"* → search `"Postgres choice"`.
- Use entity names, not pronouns. Resolve "that thing" from recent context first.
- Don't search on meta-questions ("what was that?") — use recent context or `get_memories` ordered by `created_at`.

**Metadata filters** match the same `type` values written under "After completing significant work" below.

Two rules from the v2 filter spec:

1. The root **must** be a logical operator (`AND` / `OR` / `NOT`) with an array. A bare `{"user_id": "..."}` won't work.
2. Metadata uses a **nested** object, not a dotted key. `{"metadata": {"type": "decision"}}`, never `{"metadata.type": "decision"}`. Only top-level metadata keys are filterable.

Combine `user_id` + `app_id` with one metadata clause per call:

| `metadata.type` clause | Use for |
|--------|---------|
| `{"metadata": {"type": "decision"}}` | design / architecture / "how should we" questions |
| `{"metadata": {"type": "anti_pattern"}}` | debugging, error handling, things that failed before |
| `{"metadata": {"type": "user_preference"}}` | tooling, stack, style — always include for code work |
| `{"metadata": {"type": "convention"}}` | established patterns in this project |

### Which categories to search by query intent

When a query clearly maps to one of the platform's custom categories, fan-out to 2–3 parallel `search_memories` calls scoped to those categories so recall is precise without being noisy. Use the `metadata.type` filter as your primary discriminator; treat the category column below as the semantic lens to pick the right query nouns.

| User intent / signal | Primary categories to search | Example query nouns |
|---|---|---|
| Design or architecture question | `architecture_decisions`, `api_contracts`, `data_model` | `"architecture decision"`, `"API schema"`, `"data model"` |
| Something failed / debugging | `anti_patterns`, `bug_fixes`, `security_constraints` | `"bug root cause"`, `"failure pattern"`, `"security constraint"` |
| How do we do X here? | `coding_conventions`, `team_norms`, `testing_patterns` | `"code convention"`, `"team norm"`, `"test strategy"` |
| Which library / version to use | `dependency_decisions`, `tooling_setup`, `architecture_decisions` | `"dependency choice"`, `"library version"`, `"tooling setup"` |
| Performance or scale concern | `performance_findings`, `architecture_decisions`, `data_model` | `"performance bottleneck"`, `"profiling result"`, `"optimisation"` |
| Security / auth / compliance | `security_constraints`, `api_contracts`, `coding_conventions` | `"auth rule"`, `"security requirement"`, `"compliance"` |
| Test strategy or coverage | `testing_patterns`, `coding_conventions`, `anti_patterns` | `"test framework"`, `"coverage target"`, `"fixture pattern"` |
| Schema / DB / domain object | `data_model`, `api_contracts`, `domain_glossary` | `"schema"`, `"column"`, `"domain object"` |
| API shape or versioning | `api_contracts`, `data_model`, `architecture_decisions` | `"endpoint"`, `"request schema"`, `"versioning"` |
| How to deploy / release / rollback | `deployment_runbook`, `tooling_setup`, `team_norms` | `"deploy step"`, `"rollback"`, `"CI pipeline"` |
| Team process / branching / PRs | `team_norms`, `coding_conventions`, `deployment_runbook` | `"branching strategy"`, `"PR review"`, `"working agreement"` |
| What does this term mean? | `domain_glossary`, `data_model`, `api_contracts` | `"glossary"`, `"abbreviation"`, `"domain term"` |
| Experiment / spike / A-B test | `experiment_results`, `performance_findings`, `anti_patterns` | `"experiment result"`, `"A/B test"`, `"spike outcome"` |
| User's tool / language preferences | `user_preferences`, `tooling_setup`, `coding_conventions` | `"user preference"`, `"preferred tool"`, `"language choice"` |
| Past task strategies that worked | `task_learnings`, `anti_patterns`, `coding_conventions` | `"task strategy"`, `"approach that worked"` |
| Environment / setup question | `tooling_setup`, `deployment_runbook`, `dependency_decisions` | `"environment setup"`, `"build tool"`, `"install step"` |
| Anything related to current state | `task_learnings`, `architecture_decisions`, `anti_patterns` | (combine with recency filter — see below) |

Full filter (replace `<your_user_id>` and `<your_project_id>` with the active values from SessionStart):
```python
filters={"AND": [{"user_id": "<your_user_id>"}, {"app_id": "<your_project_id>"}, {"metadata": {"type": "decision"}}]}
```

### Worked example

User asks: *"Refactor the auth module to use JWT."*

Don't:
```python
search_memories(query="Refactor the auth module to use JWT")
# Hits whatever shares words. Misses prior decisions and preferences.
```

Do (parallel — substitute the active `user_id` and `app_id` for the placeholders):
```python
search_memories(query="auth module decisions",
                filters={"AND": [{"user_id": "<your_user_id>"}, {"app_id": "<your_project_id>"}, {"metadata": {"type": "decision"}}]})
search_memories(query="JWT",
                filters={"AND": [{"user_id": "<your_user_id>"}, {"app_id": "<your_project_id>"}]})
search_memories(query="auth refactor failures",
                filters={"AND": [{"user_id": "<your_user_id>"}, {"app_id": "<your_project_id>"}, {"metadata": {"type": "anti_pattern"}}]})
search_memories(query="auth",
                filters={"AND": [{"user_id": "<your_user_id>"}, {"app_id": "<your_project_id>"}, {"metadata": {"type": "user_preference"}}]})
```

## After completing significant work

Extract key learnings and store them using the `add_memory` tool:

- **Decisions made** -> Include metadata `{"type": "decision"}`
- **Strategies that worked** -> Include metadata `{"type": "task_learning"}`
- **Failed approaches** -> Include metadata `{"type": "anti_pattern"}`
- **User preferences observed** -> Include metadata `{"type": "user_preference"}`
- **Environment/setup discoveries** -> Include metadata `{"type": "environmental"}`
- **Conventions established** -> Include metadata `{"type": "convention"}`

Always include `"branch": "<active_branch>"` in the metadata object alongside `type`. The active branch is shown in the SessionStart banner. This enables branch-scoped filtering later (e.g., "what did we do on feature/auth-rewrite?").

> `metadata.type` (which you set explicitly) and `categories` (which the platform auto-tags after the project's custom-category list — see `scripts/setup_coding_categories.py`) are complementary. Always set `metadata.type` for explicit filtering; the platform fills in `categories` on its own. Don't try to set `categories` on `add_memory` calls — per-request overrides aren't supported on the managed API.

### Expiration: high-churn vs durable

Some memory types are state snapshots that go stale fast; others are durable facts that should outlive the session that created them. Mark the difference with `expiration_date` on writes.

| Type | Expiration | Why |
|---|---|---|
| `session_state`, `compact_summary` | `expiration_date` ≈ today + 90 days | Describe a single moment of project state. Useless after a quarter; clutter the recall surface. |
| `decision`, `anti_pattern`, `convention`, `user_preference`, `task_learning`, `environmental` | omit `expiration_date` | Durable facts. A decision made last year is still a decision; same for a convention or a user preference. |

`add_memory` accepts `expiration_date` as a string (`"YYYY-MM-DD"`). The two server-side hooks (`on_pre_compact.py`, `capture_compact_summary.py`) already set this for the types they write. When you write directly via the MCP tool, follow the same rule.

### Recency filter on recall

When the user is asking about *current* state ("where were we", "what's the active task", "the latest decision on X"), filter recall to recent memories so stale snapshots don't surface:

```python
# Last 90 days only
{"AND": [{"user_id": "<id>"}, {"app_id": "<your_project_id>"}, {"metadata": {"type": "session_state"}}, {"created_at": {"gte": "<90 days ago, YYYY-MM-DD>"}}]}
```

Skip the recency filter when the user is asking about durable facts ("what conventions does this project use", "have we hit this bug before") — those are timeless and recency would hide them.

Memories can be as detailed as needed -- include full context, reasoning, code snippets, file paths, and examples. Longer, searchable memories are more valuable than vague one-liners.

### Use `infer=False` for already-structured content

When you've done the extraction work yourself — pre-compaction summaries, decisions, anti-patterns, conventions you've explicitly identified — pass `infer=False` so the platform stores your text verbatim instead of running a second extraction pass over it.

```python
add_memory(
    messages=[{"role": "user", "content": "<your structured fact>"}],
    user_id="<active user_id>",
    app_id="<active project_id>",
    metadata={"type": "decision", "branch": "<active branch>"},
    infer=False,
)
```

Stick to one mode per distinct piece of content — don't mix `infer=True` (default) and `infer=False` for the same fact, you'll get duplicates. Default (`infer=True`) is right for raw conversational signal you want extracted; `infer=False` is right for pre-extracted structure.

## Before losing context

If context is about to be compacted or the session is ending, store a comprehensive session summary:

```
## Session Summary

### User's Goal
[What the user originally asked for]

### What Was Accomplished
[Numbered list of tasks completed]

### Key Decisions Made
[Architectural choices, trade-offs discussed]

### Files Created or Modified
[Important file paths with what changed]

### Current State
[What is in progress, pending items, next steps]
```

Include metadata: `{"type": "session_state"}`

## Inline citations

When your response is informed by specific memories, cite them so the user can trace provenance. Use the memory ID returned by `search_memories`.

Format: `[mem0:<short_id>]` where `<short_id>` is the first 8 characters of the memory ID.

Example:
> We chose Postgres over SQLite for production [mem0:a3f8b2c1] and the auth module uses JWT tokens [mem0:7e2d9f4a].

Rules:
- Only cite when the memory **directly informed** your answer. Don't cite for general knowledge.
- Place citations inline, at the end of the relevant sentence.
- If multiple memories support the same point, cite all: `[mem0:abc12345][mem0:def67890]`.
- Don't cite `session_state` or `compact_summary` memories — those are internal bookkeeping.
- Keep it subtle. One or two citations per response is typical. Don't over-cite.

## Memory hygiene

- Do NOT write to MEMORY.md or any file-based memory. Use mem0 MCP tools exclusively.
- Only store genuinely useful learnings. Skip trivial interactions.
- Use specific, searchable language in memory content.

### Confidence scoring on every add_memory

Every `add_memory` call MUST include a `confidence` field in its `metadata` object. This captures how certain the stored fact is, so downstream callers can filter out speculation.

| `metadata.confidence` value | Meaning | When to use |
|---|---|---|
| `1.0` | User explicitly stated it | User said "we use Postgres", "always lint before commit", "never use floats for currency" |
| `0.8` | Observed directly in code / config | You read it from a file, migration, or config — not inferred |
| `0.5` | Inferred from context | You derived it from surrounding evidence but the user didn't confirm it |
| `0.3` | Guessed / low-signal | Extrapolated from a single weak signal; treat as a tentative hypothesis |

Example:

```python
add_memory(
    messages=[{"role": "user", "content": "We always use Postgres — never SQLite in production."}],
    user_id="<active user_id>",
    app_id="<active project_id>",
    metadata={"type": "architecture_decisions", "branch": "<active branch>", "confidence": 1.0},
    infer=False,
)
```

**Search guidance:** When recalling actionable facts (decisions, conventions, security constraints), optionally apply a confidence threshold of 0.6 or above to avoid surfacing low-confidence guesses. Only top-level metadata keys are filterable, so `confidence` filtering requires SDK-side post-filtering or a dedicated high-confidence write path — for now, include the confidence value in every write and document it in the memory content so it is searchable via text.

### File path tagging on every add_memory

Every `add_memory` call that is associated with specific files MUST include a `files` key in its `metadata` object. The value is an array of affected file paths relative to the project root.

```python
add_memory(
    messages=[{"role": "user", "content": "The auth middleware lives in src/middleware/auth.ts and validates JWTs using the shared key in config/secrets.ts."}],
    user_id="<active user_id>",
    app_id="<active project_id>",
    metadata={
        "type": "architecture_decisions",
        "branch": "<active branch>",
        "confidence": 0.8,
        "files": ["src/middleware/auth.ts", "config/secrets.ts"],
    },
    infer=False,
)
```

**Filtering note:** The mem0 v2 filter API does not yet support `array-contains` predicates. You cannot filter by `metadata.files` at search time. To work around this, always embed the bare filenames (and important path segments) in the memory content text itself — the vector search will then surface them on a filename query. The `files` array in metadata is still written for future compatibility once array-contains filtering is available.

### Access counter: track memory usage

When you retrieve a memory via `search_memories` and **actually use it** in your response (i.e., it informed your answer or you cited it), increment its access counter by calling:

```python
# 1. Read current state
mem = get_memory(memory_id=<id>)
current_text = mem["content"]  # or mem["memory"], depending on response shape

# 2. Update with access_count bump
update_memory(
    memory_id=<id>,
    data=current_text,  # preserve original text — required parameter
)
```

**Important:** `update_memory` requires the `data` (text) parameter. Always `get_memory` first to read the current content, then pass it back unchanged. A metadata-only update may error or wipe the content.

**When to increment:** Only when you actually used the memory to answer. Don't bump on every search hit — that inflates counts for memories that were returned but irrelevant. Aim for 1-3 bumps per response at most.

**Why:** Access counts feed into `/mem0:dream` pruning decisions. Memories that are never accessed after creation are candidates for cleanup. Frequently accessed memories are protected from pruning regardless of age.
