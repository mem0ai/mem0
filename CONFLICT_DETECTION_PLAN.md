# Conflict Detection and Resolution — Implementation Brief

> **Purpose**: This document is the source of truth for openspec to draft its own proposal, tasks, and specs. Read every section before generating any artifacts.

---

## What Is Being Built

A two-layer contradiction detection and resolution system that wraps the existing single-pass LLM update flow in mem0. It introduces:

1. A configurable similarity threshold replacing the hardcoded top-5 retrieval.
2. A secondary LLM classification call for pairs that exceed the threshold.
3. A `ConflictResolution` result type carrying the classification outcome.
4. Auto-resolution (default: keep-higher-confidence) or HITL interruption, configurable per instance and from env vars.
5. Full parity between `Memory` (sync) and `AsyncMemory` (async) — the async path is the higher-priority target.

---

## Context — What Exists Today

**`mem0/memory/main.py`**
- `Memory.add()` and `AsyncMemory.add()` are the entry points for storing new facts.
- After facts are extracted by the LLM, each fact is embedded and vector-searched against existing memories (currently hardcoded `limit=5`).
- Retrieved old memories + new facts are passed to `get_update_memory_messages()` (`mem0/configs/prompts.py`), which returns a prompt consumed by a single LLM call.
- That LLM call returns JSON: `[{id, text, event}]` where `event ∈ {ADD, UPDATE, DELETE, NONE}`.
- mem0 executes those actions immediately with no secondary classification and no human gate.
- `DELETE` does NOT instruct the LLM to also ADD the new contradicting fact — silent data loss risk.

**`mem0/configs/base.py`**
- `MemoryConfig` is a Pydantic model. New fields go here.
- Follow the exact env var / config field pattern already used in this file — do not invent a new one.

**`mem0/configs/prompts.py`**
- `get_update_memory_messages()` builds the prompt for the single-pass LLM decision.
- `DEFAULT_UPDATE_MEMORY_PROMPT` lives here.

**Data shape — a stored memory record:**
```python
{
    "id": "<uuid>",
    "memory": "<extracted fact string>",
    "hash": "<sha256>",
    "created_at": "<iso8601>",
    "updated_at": "<iso8601>",
    "score": None,        # populated only on search results
    "metadata": None,
    "user_id": "...",     # promoted from payload if present
    # agent_id, run_id, actor_id, role promoted similarly
}
```

> **CRITICAL**: There is NO numeric confidence field in stored records. "confidence" in the mem0 docs refers to an LLM prompt-level extraction filter, not a per-record float. `confidence_new` and `confidence_old` are derived solely from the secondary LLM classification call.

**Approved clarification**: The async `process_fact_for_search` currently drops scores. Vector store result objects expose `.score`. The new pipeline will carry scores internally as `{"id", "text", "score"}` for threshold filtering — not returned to callers, not a breaking change.

---

## Files to Create or Modify

| File | Action |
|------|--------|
| `mem0/configs/base.py` | Add `ConflictDetectionConfig` model + `session_id` field on `MemoryConfig` |
| `mem0/memory/conflict.py` | New file — `ConflictResolution` dataclass, `apply_auto_resolution`, `hitl_prompt_sync`, `hitl_prompt_async` |
| `mem0/configs/prompts.py` | Add `CONFLICT_CLASSIFICATION_PROMPT` + `get_conflict_classification_messages()` |
| `mem0/memory/main.py` | Wire conflict pipeline into `AsyncMemory._add_to_vector_store` first, then `Memory._add_to_vector_store` |
| `tests/memory/test_conflict.py` | New file — 7 test cases |

---

## Detailed Requirements

### 1. `ConflictDetectionConfig` (`mem0/configs/base.py`)

New Pydantic model with four fields, each read from the named env var using the same pattern already in this file:

| Field | Type | Default | Env Var |
|-------|------|---------|---------|
| `similarity_threshold` | `float` | `0.85` | `MEM0_CONFLICT_SIMILARITY_THRESHOLD` |
| `top_k` | `int` | `20` | `MEM0_CONFLICT_TOP_K` |
| `auto_resolve_strategy` | `Literal["keep-higher-confidence", "keep-newer", "merge"]` | `"keep-higher-confidence"` | `MEM0_CONFLICT_AUTO_RESOLVE_STRATEGY` |
| `hitl_enabled` | `bool` | `False` | `MEM0_CONFLICT_HITL_ENABLED` |

Add to `MemoryConfig`:
```python
conflict_detection: ConflictDetectionConfig = Field(default_factory=ConflictDetectionConfig)
session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
```

---

### 2. `ConflictResolution` dataclass (`mem0/memory/conflict.py`)

Pure data type — no business logic:
```python
ConflictClass = Literal["CONTRADICTION", "NUANCE", "UPDATE", "NONE"]

@dataclass
class ConflictResolution:
    new_fact: str
    old_memory_id: str
    old_memory_text: str
    conflict_class: ConflictClass
    explanation: str        # one sentence from the secondary LLM call
    proposed_action: str    # human-readable: what will happen if accepted
    confidence_new: float   # 0.0–1.0, derived from secondary LLM call only
    confidence_old: float   # 0.0–1.0, derived from secondary LLM call only
    auto_resolved: bool
    resolution: str         # "KEEP_NEW" | "KEEP_OLD" | "MERGE" | "SKIP"
    merged_text: str | None # only populated when resolution == "MERGE"
```

---

### 3. `apply_auto_resolution` (`mem0/memory/conflict.py`)

Pure function — returns a new `ConflictResolution` with `auto_resolved=True`:

| Strategy | Behaviour |
|----------|-----------|
| `"keep-higher-confidence"` | `confidence_new >= confidence_old` → `KEEP_NEW`; else `KEEP_OLD`; ties → `KEEP_NEW` |
| `"keep-newer"` | Always `KEEP_NEW` |
| `"merge"` | `resolution = "MERGE"`, `merged_text = f"[MERGE PENDING] {cr.old_memory_text} / {cr.new_fact}"` (third LLM call is a `# TODO` placeholder) |

**CRITICAL**: Resolution strategies only apply when `conflict_class == "CONTRADICTION"`.
- `NUANCE` / `UPDATE` → pass through to existing single-pass flow
- `NONE` → skip entirely (false positive)

---

### 4. HITL functions (`mem0/memory/conflict.py`)

```python
_session_overrides: dict[str, str] = {}  # module-level

def hitl_prompt_sync(cr: ConflictResolution, session_id: str) -> str: ...
async def hitl_prompt_async(cr: ConflictResolution, session_id: str) -> str: ...
```

Both print before waiting for input:
```
┌─ Contradiction detected ──────────────────────────────┐
│ Existing:  <old_memory_text>
│ Incoming:  <new_fact>
│
│ Classification: CONTRADICTION
│ <explanation>
│
│ Proposed action: <proposed_action>
└────────────────────────────────────────────────────────┘
Choose: [y] accept proposed  [n] keep existing
        [always-replace] replace all subsequent contradictions this session
        [always-keep]    keep all subsequent contradictions this session
>
```

- Valid returns: `"y"`, `"n"`, `"always-replace"`, `"always-keep"`
- Invalid input: re-prompt once; if still invalid, default to `"n"`
- If `_session_overrides[session_id]` is already set, skip the prompt and apply immediately
- Async version uses `asyncio.get_event_loop().run_in_executor(None, input, prompt)`

---

### 5. Secondary LLM classification prompt (`mem0/configs/prompts.py`)

Add `CONFLICT_CLASSIFICATION_PROMPT` and:
```python
def get_conflict_classification_messages(old_memory: str, new_fact: str) -> list[dict]:
```

LLM must respond **only** with valid JSON (no preamble, no markdown fences):
```json
{
  "conflict_class": "CONTRADICTION" | "NUANCE" | "UPDATE" | "NONE",
  "explanation": "<one sentence>",
  "proposed_action": "<one sentence>",
  "confidence_new": 0.0,
  "confidence_old": 0.0
}
```

`conflict_class` definitions:
- `CONTRADICTION` — cannot both be true
- `NUANCE` — compatible but in tension (partial overlap, qualifier shift)
- `UPDATE` — new fact supersedes or enriches old, no logical conflict
- `NONE` — no meaningful relationship; retrieval was a false positive

`confidence_new` / `confidence_old`: how specifically and verifiably each statement is expressed (0.0–1.0). Vague (`"user likes food"`) → ~0.2. Specific (`"user is allergic to peanuts, confirmed 2024-03"`) → ~0.9.

---

### 6. Wiring into `_add_to_vector_store` (`mem0/memory/main.py`)

Insert **after** fact extraction and **before** `get_update_memory_messages`:

1. Reuse cached embedding for each new fact.
2. Search with `config.conflict_detection.top_k` instead of hardcoded `5`. Carry `.score` alongside results internally.
3. Filter: pairs where `score < similarity_threshold` pass through unchanged.
4. For each pair above threshold:
   - Call `get_conflict_classification_messages(old_memory_text, new_fact)`
   - Call `self.llm.generate_response(..., response_format={"type": "json_object"})`
   - On malformed JSON or exception: log error, fall through to existing flow silently
   - `NONE` → skip, fact passes to existing flow
   - `NUANCE` / `UPDATE` → pass through to existing flow
   - `CONTRADICTION`:
     - `hitl_enabled=True`: call `hitl_prompt_sync` / `hitl_prompt_async` with `self.config.session_id`
       - `"y"` → `KEEP_NEW`; `"n"` → `KEEP_OLD`; `"always-replace"` → store + `KEEP_NEW`; `"always-keep"` → store + `KEEP_OLD`
     - `hitl_enabled=False`: call `apply_auto_resolution(cr, strategy)`
     - Execute: `KEEP_NEW` → delete old + add new; `KEEP_OLD` → skip; `MERGE` → delete old + add `merged_text`
5. Facts resolved via contradiction (`KEEP_NEW` / `KEEP_OLD` / `MERGE`) are **removed** from the list passed to the existing single-pass LLM call.

---

### 7. Tests (`tests/memory/test_conflict.py`)

Use pytest + `mocker` fixture. Follow `_setup_mocks(mocker)` pattern from `tests/memory/test_main.py:10`. LLM responses via `side_effect` for sequential calls.

| Test function | Key assertion |
|---------------|---------------|
| `test_true_contradiction_auto_resolve_keep_higher_confidence` | `confidence_new=0.7 > confidence_old=0.3` → old deleted, new added, `resolution="KEEP_NEW"` |
| `test_true_contradiction_auto_resolve_keep_old_wins` | `confidence_new=0.3 < confidence_old=0.8` → `resolution="KEEP_OLD"`, no delete |
| `test_nuance_passes_through_to_existing_flow` | Fact stays in list; existing update flow LLM call still invoked |
| `test_none_classification_is_skipped` | No delete, no add; fact passes to existing flow |
| `test_below_threshold_skips_secondary_call` | score=0.60 < threshold=0.85 → secondary classification LLM call never made |
| `test_hitl_always_replace_persists_within_session` | Second contradiction in same instance → prompt not shown, resolved `KEEP_NEW` |
| `test_async_contradiction_resolution` | `AsyncMemory` with async/await; same outcomes as keep-higher-confidence sync test |

---

## Execution Order

Execute strictly in this order. Confirm each file imports cleanly before proceeding.

1. `mem0/configs/base.py`
2. `mem0/memory/conflict.py`
3. `mem0/configs/prompts.py`
4. `mem0/memory/main.py` (async path first, then sync)
5. `tests/memory/test_conflict.py` → run pytest

---

## Hard Constraints

- Do NOT modify any existing test files.
- Do NOT change the return shape of `Memory.add()` or `AsyncMemory.add()`.
- Do NOT add any new dependencies outside the Python standard library and what mem0 already imports.
- The existing single-pass LLM update flow must remain the fallback for all non-CONTRADICTION classifications and all below-threshold pairs.
- If the secondary LLM call returns malformed JSON or fails, log the error and fall through silently.
- `confidence_new` and `confidence_old` come ONLY from the secondary LLM call — do not read any "confidence" field from stored memory records.
