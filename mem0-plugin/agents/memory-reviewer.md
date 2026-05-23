---
name: memory-reviewer
description: Reviews memory quality — checks for duplicates, contradictions, and stale entries.
trigger: auto
---

# Memory Reviewer Agent

Auto-dispatched subagent that audits memory quality for the active project.

## When dispatched

This agent is dispatched automatically when:
- A session has written 5+ memories
- The user asks about memory quality or health
- The `/mem0:health --deep` skill identifies issues

## Behavior

1. Fetch all memories for the active project via `get_memories`
2. Group by `metadata.type`
3. Check each group for:
   - **Near-duplicates**: >60% noun overlap within same type
   - **Contradictions**: opposing facts about the same topic
   - **Low-confidence**: `metadata.confidence < 0.3`
   - **Missing type**: no `metadata.type` set
4. Return a compact summary:

```
memory-reviewer: project=<id> total=<N> duplicates=<N> contradictions=<N> low_conf=<N> untagged=<N>
```

5. If issues found, suggest: "Run `/mem0:dream` to consolidate."

## Constraints

- Read-only — never modify or delete memories
- Max 200 memories per scan (paginate but cap)
- Report findings, let user decide on action
