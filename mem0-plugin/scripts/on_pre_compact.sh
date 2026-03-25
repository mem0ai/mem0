#!/usr/bin/env bash
# Hook: PreCompact
#
# Fires BEFORE context compaction. This is the last chance to capture
# the full context before it gets compressed.
#
# Output: Text instructions injected into Claude's context.
# Claude still has the full conversation and can write an accurate summary.
# A companion Python script (on_pre_compact.py) also runs to capture
# transcript state directly via the Mem0 REST API as a safety net.

set -euo pipefail

cat <<'EOF'
## CRITICAL: Pre-Compaction Session Summary

Context compaction is about to happen. You are about to lose most of your conversation history. You MUST store a comprehensive session summary NOW using the mem0 `add_memory` tool.

### Step 1: Store session summary

Call `add_memory` with a thorough summary covering ALL of the following:

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

Include metadata: `{"type": "session_state", "source": "pre-compaction"}`

### Step 2: Store any unstored learnings

If there are learnings from this session that you haven't stored yet, store them as separate memories:
- Failed approaches -> metadata `{"type": "anti_pattern"}`
- Successful strategies -> metadata `{"type": "task_learning"}`
- Architecture decisions -> metadata `{"type": "decision"}`

### Step 3: Acknowledge

After storing, briefly tell the user that session state has been saved and you're ready for compaction.

Do this NOW. Do not skip any section. The quality of this summary directly determines whether you can continue the user's task after compaction.
EOF

exit 0
