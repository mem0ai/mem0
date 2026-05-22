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

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INPUT=$(cat)

python3 "$SCRIPT_DIR/telemetry.py" pre_compact 2>/dev/null &

cat <<'EOF'
## Pre-Compaction: Extract and store durable facts

Context compaction is about to happen. Review the conversation and store only facts that would help a future agent with ZERO context.

### What to store

For each fact, ask: "Would a new agent — with no prior context — benefit from knowing this?" If no, skip it. Most sessions produce 0-3 facts worth storing.

Store each fact as a SEPARATE `add_memory` call. One fact per call. 15-50 words each. Third person. Include file paths when relevant.

Categories and when to use them:
- `decision` — architectural choices, trade-offs made ("Chose PostgreSQL over MongoDB for auth because of ACID requirements")
- `task_learning` — patterns that worked ("Running migrations before seed in this repo avoids FK violations")
- `anti_pattern` — approaches that failed ("Don't use batch insert for users table — triggers deadlock with audit log")
- `convention` — coding standards discovered ("This repo uses snake_case for all Python files, camelCase for TS")
- `user_preference` — how the user likes to work ("User prefers short PRs, one feature per branch")

### What NOT to store

- Session summaries or "what we did today" blobs
- Raw file lists or command histories
- Anything already stored in a prior `add_memory` this session
- One-time information that won't recur
- Transient state ("currently debugging X")

### How to store

```
add_memory(
  messages=[{"role":"user","content":"<one fact, 15-50 words>"}],
  user_id="<active user_id>",
  app_id="<active project_id>",
  metadata={"type":"<category>","branch":"<active branch>","confidence":0.8},
  infer=False,
)
```

If nothing durable happened this session, store nothing. That is correct.
EOF

exit 0
