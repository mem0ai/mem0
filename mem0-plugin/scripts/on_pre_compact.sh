#!/usr/bin/env bash
# Hook: PreCompact
#
# Fires BEFORE context compaction. This is the last chance to capture
# the full context before it gets compressed.
#
# Output: Text instructions injected into Claude's context.
# Claude still has the full conversation and can write an accurate summary,
# which it stores via add_memory(infer=False) so the platform preserves
# the structure verbatim instead of running a second extraction pass.

set -euo pipefail

if [ -n "${MEM0_DEBUG:-}" ]; then
  mkdir -p "$HOME/.mem0" && exec 2>>"$HOME/.mem0/hooks.log"
fi

cat <<'EOF'
## CRITICAL: Pre-Compaction Session Summary

Context compaction is about to happen. You are about to lose most of your conversation history. You MUST store a comprehensive session summary NOW using the mem0 `add_memory` tool.

### Step 1: Store session summary

Call `add_memory` with `infer=False` and a thorough summary covering ALL of the following.

`infer=False` is critical here: you've already done the extraction work yourself using full context. Without it, the platform runs a second LLM pass that loses your structure and pulls fragmented facts. With it, your summary is preserved verbatim.

```
## Session Summary (Pre-Compaction)

### User's Goal
[What the user originally asked for and their intent]

### What Was Accomplished
[Numbered list of tasks completed, features built, bugs fixed]

### Key Decisions Made
[Architectural choices, design decisions, trade-offs discussed]

### Files Created or Modified
[List of important file paths with what changed in each]

### Current State
[What is in progress RIGHT NOW — the task you were in the middle of]
[Any pending items, blockers, or next steps]

### Important Context
[User preferences observed, coding patterns, anything that would help
the post-compaction agent continue without asking redundant questions]
```

Tool call shape:
```
add_memory(
  messages=[{"role":"user","content":"<the summary above>"}],
  user_id="<the active user_id from the SessionStart bootstrap>",
  metadata={"type":"session_state","source":"pre-compaction"},
  infer=False,
)
```

### Step 2: Store any unstored learnings

If there are learnings from this session that you haven't stored yet, store them as separate memories with `infer=False` (same reasoning -- you've already extracted the fact, don't re-extract):
- Failed approaches -> metadata `{"type": "anti_pattern"}`
- Successful strategies -> metadata `{"type": "task_learning"}`
- Architecture decisions -> metadata `{"type": "decision"}`

### Step 3: Acknowledge

After storing, briefly tell the user that session state has been saved and you're ready for compaction.

Do this NOW. Do not skip any section. The quality of this summary directly determines whether you can continue the user's task after compaction.
EOF

exit 0
