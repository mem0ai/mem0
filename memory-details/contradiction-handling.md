# How mem0 Handles Contradictory Entries

## The Core Mechanism: Fully Automated LLM Arbitration

Contradiction resolution is delegated entirely to an LLM via the `DEFAULT_UPDATE_MEMORY_PROMPT`.
There is no human approval gate, no pending queue, and no review workflow.

**The pipeline (`main.py:549–601`):**

1. Each new extracted fact is embedded and used to vector-search for semantically similar existing memories (top-5).
2. The retrieved old memories + new facts are fed to the LLM via `get_update_memory_messages`.
3. The LLM responds with a JSON array of `{id, text, event}` objects — each labeled `ADD`, `UPDATE`, `DELETE`, or `NONE`.
4. mem0 executes those actions immediately, no pause.

```python
# main.py:574-582
function_calling_prompt = get_update_memory_messages(
    retrieved_old_memory, new_retrieved_facts, self.config.custom_update_memory_prompt
)

response: str = self.llm.generate_response(
    messages=[{"role": "user", "content": function_calling_prompt}],
    response_format={"type": "json_object"},
)
```

---

## How `custom_update_memory_prompt` Is Assigned

The argument follows a three-step chain before reaching `get_update_memory_messages`.

**1. Declared as an optional field on `MemoryConfig` (`configs/base.py:63-66`)**

```python
custom_update_memory_prompt: Optional[str] = Field(
    description="Custom prompt for the update memory",
    default=None,
)
```

It defaults to `None` unless the user passes a string at construction time.

**2. Mirrored onto the `Memory` instance at `__init__` (`main.py:249`)**

```python
self.custom_update_memory_prompt = self.config.custom_update_memory_prompt
```

Note: this instance attribute is never read again — both call sites read
`self.config.custom_update_memory_prompt` directly, so this line is effectively dead code.

**3. Passed into `get_update_memory_messages` at call time (`main.py:574-576`)**

```python
function_calling_prompt = get_update_memory_messages(
    retrieved_old_memory, new_retrieved_facts, self.config.custom_update_memory_prompt
)
```

**4. Falls back to `DEFAULT_UPDATE_MEMORY_PROMPT` if `None` (`prompts.py:405-408`)**

```python
def get_update_memory_messages(retrieved_old_memory_dict, response_content, custom_update_memory_prompt=None):
    if custom_update_memory_prompt is None:
        global DEFAULT_UPDATE_MEMORY_PROMPT
        custom_update_memory_prompt = DEFAULT_UPDATE_MEMORY_PROMPT
```

From the user's perspective, to override it:

```python
m = Memory(config=MemoryConfig(custom_update_memory_prompt="Your prompt here..."))
```

If not set, `DEFAULT_UPDATE_MEMORY_PROMPT` (the full ADD/UPDATE/DELETE/NONE instruction block)
is used unconditionally.

---

## The Contradiction-Specific Instructions in the Prompt

The prompt distinguishes two contradictory scenarios with different prescribed actions:

**Soft contradiction (same topic, richer info) → UPDATE:**

```
2. **Update**: If the retrieved facts contain information that is already present in the memory
but the information is totally different, then you have to update it.
Example (a) -- if the memory contains "User likes to play cricket" and the retrieved fact is
"Loves to play cricket with friends", then update the memory with the retrieved facts.
```

**Hard contradiction (opposing facts) → DELETE:**

```
3. **Delete**: If the retrieved facts contain information that contradicts the information present
in the memory, then you have to delete it.
```

*(`configs/prompts.py:263`)*

The DELETE example shows "Dislikes cheese pizza" arriving when "Loves cheese pizza" exists — the old
entry is deleted. Critically, the prompt does **not** instruct the LLM to also ADD the new
contradicting fact; that is left to LLM discretion, creating a potential silent data loss path where
the new belief goes unrecorded.

---

## Graph Memory: Same Pattern, Different Prompt

All four graph backends (`graph_memory.py`, `kuzu_memory.py`, `apache_age_memory.py`,`memgraph_memory.py`) use `UPDATE_GRAPH_PROMPT`, which also delegates conflict to the LLM:

```python
# graphs/utils.py:10-13
2. Conflict Resolution:
   - If new information contradicts an existing memory:
     a) For matching source and target but differing content, update the relationship of the existing memory.
     b) If the new memory provides more recent or accurate information, update the existing memory accordingly.
```

No human gate here either.

---

## The Only Post-Hoc Audit: `db.add_history`

The one safeguard is an immutable history log written *after* every mutation — not before:

```python
# main.py:1311-1320 (_update_memory)
self.db.add_history(
    memory_id,
    prev_value,    # old content
    data,          # new content
    "UPDATE",
    created_at=new_metadata["created_at"],
    updated_at=new_metadata["updated_at"],
    actor_id=new_metadata.get("actor_id"),
    role=new_metadata.get("role"),
)
```

```python
# main.py:1337-1346 (_delete_memory)
self.db.add_history(
    memory_id,
    prev_value,
    None,
    "DELETE",
    ...
    is_deleted=1,
)
```

This is retrievable via `memory.history(memory_id)` but is purely observational — it cannot block, reject, or queue a write for human review.

---

## Human-in-the-Loop: None Exists

There is no HITL implementation for contradiction handling. Searching the entire codebase for any approval/confirmation/pending pattern turns up only:

**`response_callback`** on `OpenAIConfig` — a post-response monitoring hook for the OpenAI LLM provider only. It fires *after* the LLM generates its action plan, not after the mutations are applied, and cannot veto anything:

```python
# llms/openai.py:141-147
if self.config.response_callback:
    try:
        self.config.response_callback(self, response, params)
    except Exception as e:
        # Log error but don't propagate
        logging.error(f"Error due to callback: {e}")
        pass
```

This is an observation hook, not a gate. Exceptions are swallowed.

---

## Summary

| Mechanism | Purpose | Blocks contradictory write? |
|---|---|---|
| `DEFAULT_UPDATE_MEMORY_PROMPT` | LLM decides UPDATE vs DELETE vs NONE | No — it IS the decision |
| `UPDATE_GRAPH_PROMPT` | Same for graph backends | No |
| `db.add_history` | Audit trail after the fact | No |
| `response_callback` (OpenAI only) | LLM response monitoring | No — errors are swallowed |

**Conclusion:** mem0 handles contradictions through a single-pass, fully autonomous LLM judgment
call with no human checkpoint. The only recoverability mechanism is the history log, which enables
post-hoc inspection but not pre-write review.
