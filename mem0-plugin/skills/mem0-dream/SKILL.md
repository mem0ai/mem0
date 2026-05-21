---
name: mem0-dream
description: >
  Memory consolidation pass. Fetches all project memories, finds near-duplicates,
  merges them, flags contradictions, prunes stale entries per retention policy.
  Outputs a diff for user approval before applying changes.
  TRIGGER: user runs /mem0:dream, or asks "consolidate memories", "clean up memories",
  "merge duplicate memories", "run dream".
---

# Mem0 Dream — Memory Consolidation

This skill performs a memory consolidation pass: it fetches all project memories,
identifies near-duplicates, flags contradictions, and prunes stale entries based on
configured retention policies. All proposed changes are shown as a diff for user
approval before anything is modified.

---

## Step 1: Load Retention Policies

Determine the active retention policy by running the parser script. Use the
appropriate `PLUGIN_ROOT` variable for the current platform (`${CLAUDE_PLUGIN_ROOT}`,
`${CODEX_PLUGIN_ROOT}`, or `${CURSOR_PLUGIN_ROOT}`):

```bash
python3 "<PLUGIN_ROOT>/scripts/parse_mem0_config.py" "<cwd>"
```

Parse the JSON output (a dict of `category → days | null`). If the script fails
or returns `{}`, fall back to these built-in defaults:

| `metadata.type` | Default retention |
|---|---|
| `session_state` | 90 days |
| `compact_summary` | 90 days |
| all others | no pruning |

Store the resolved policies for use in Step 3.

---

## Step 2: Fetch ALL Project Memories

Call `get_memories` to retrieve every memory for the active project:

```python
get_memories(
    user_id="<active_user_id>",
    app_id="<active_project_id>",
    page_size=200,
)
```

If the response indicates more pages exist, paginate until all memories are fetched.
Collect the full list before proceeding. If zero memories are found, print:

```
No memories found for project <project_id>. Nothing to consolidate.
```

…and stop.

---

## Step 3: Analyze — Find Issues

Work entirely in-memory; do not modify anything yet.

Group memories by `metadata.type` (use `"unknown"` when the field is absent).
For each group, identify the following:

### 3a. Near-duplicate pairs (merge candidates)

Two memories are near-duplicates when they express the same fact or decision but
phrased differently (e.g., "Use PostgreSQL for auth" and "Auth DB is PostgreSQL").

Heuristics:
- Significant noun/keyword overlap in the memory text.
- Same `metadata.type`.
- Neither memory is pinned (`metadata.pinned != true`).

For each qualifying pair, draft a merged version that is more complete and specific
than either original.

### 3b. Contradictions

Two memories contradict when they assert opposing facts about the same topic
(e.g., "Deploy to ECS" vs. "Deploy to Vercel").

Identify the likely winner: the more recent memory with higher confidence wins.
Store both IDs and their content for user review.

### 3c. Prune candidates

A memory is a prune candidate when **any** of the following is true:

1. Its `metadata.type` has a retention policy and the memory is older than the
   configured number of days (compare `created_at` to today).
2. Its confidence score is below 0.3 AND it contains no information unique to
   this project (no file paths, identifiers, or domain-specific nouns).

**Always skip memories where `metadata.pinned == true`**, regardless of age or
confidence.

---

## Step 4: Print Diff Report (item 15)

Print a structured diff to the terminal before making any changes. Use exactly
this format:

```
## Dream — Memory Consolidation Report

### Merge proposals (<N> pairs)
MERGE [mem0:<id1>] + [mem0:<id2>] → NEW
  - Original 1: "<content of memory 1, truncated to 120 chars>"
  - Original 2: "<content of memory 2, truncated to 120 chars>"
  - Merged:     "<drafted merged content>"

### Contradictions (<N> pairs)
CONFLICT [mem0:<idA>] vs [mem0:<idB>]
  - A: "<content>" (<created_at date>, confidence: <score>)
  - B: "<content>" (<created_at date>, confidence: <score>)
  Which is current? [A/B/skip]

### Prune candidates (<N> memories)
PRUNE [mem0:<id>] — <metadata.type>, <age>d old (policy: <policy_days>d)

---
Proposed: <N> merges, <N> prunes, <N> conflicts
Apply? [Y/n]
```

If there are zero items in any category, omit that section entirely.

If there are zero total proposals (no merges, no prunes, no conflicts), print:

```
Dream complete. No duplicate, contradictory, or stale memories found.
```

…and stop.

---

## Step 5: Wait for User Input and Apply

### 5a. Contradictions

For each `CONFLICT` pair in the report, wait for the user to type `A`, `B`, or
`skip` (case-insensitive). If they enter nothing (empty), treat as `skip`.

Record the winner for each pair before proceeding to the final apply confirmation.

### 5b. Final confirmation

After all conflict resolutions are collected, prompt:

```
Apply? [Y/n]
```

If the user types `n` or `no` (case-insensitive), print `Cancelled. No changes made.`
and stop.

If the user confirms (`Y`, `yes`, or empty / Enter), apply all changes in this order:

#### Merges

For each approved merge pair:
1. `delete_memory(<id1>)`
2. `delete_memory(<id2>)`
3. `add_memory` with:
   - `messages=[{"role": "user", "content": "<merged content>"}]`
   - `user_id=<active_user_id>`
   - `app_id=<active_project_id>` (top-level, not in metadata)
   - `metadata={"type": "<original type>", "branch": "<active_branch>", "confidence": <higher of the two original scores>, "source": "mem0-dream"}`
   - `infer=False`

#### Contradictions (resolved)

For each resolved conflict where the user chose A or B:
- Identify the loser (the non-chosen memory).
- First call `get_memory(<loser_id>)` to read its current text content.
- Then call `update_memory(<loser_id>, data=<original_text_content>)` to preserve the text while updating it.
- **Important:** `update_memory` requires the `data` (text) parameter. A metadata-only call may error or wipe the content. Always read first, then update with the original text.

Contradictions where the user chose `skip` are left untouched.

#### Prunes

For each prune candidate:
- `delete_memory(<memory_id>)`

---

## Step 6: Print Summary

After all changes are applied, print:

```
Dream complete.
  Merged:  <N> pairs → <N> new memories
  Pruned:  <N> memories deleted
  Flagged: <N> contradictions resolved, <N> skipped
```

---

## Auto mode

When invoked with `--auto` (e.g., `/mem0:dream --auto`), run non-interactively:

- **Merges**: applied automatically (no contradiction, both are compatible).
- **Prunes**: applied automatically (age/confidence-based, no ambiguity).
- **Contradictions**: skipped — they require human judgment.

In auto mode:
1. Load policies and fetch memories (Steps 1–3) as normal.
2. Apply merges and prunes silently without printing the diff or prompting.
3. Print a compact summary:
   ```
   [mem0-dream --auto] project=<id>  merged=<N>  pruned=<N>  conflicts_skipped=<N>
   ```
4. If contradictions were detected but skipped, store a reminder memory:
   ```python
   add_memory(
       messages=[{"role": "user", "content": "mem0-dream detected <N> contradiction(s) requiring manual review. Run /mem0:dream to resolve them interactively."}],
       user_id="<active_user_id>",
       app_id="<active_project_id>",
       metadata={"type": "task_learning", "source": "mem0-dream-auto", "branch": "<active_branch>"},
       infer=False,
   )
   ```

## Scheduling recurring dreams

When invoked with `--schedule` (e.g., `/mem0:dream --schedule weekly`), register a
cloud routine via Claude Code's built-in `/schedule` command so the dream runs
automatically without any local cron or launchd setup.

### Step S1: Parse schedule frequency

Accept natural-language frequency after `--schedule`:

| User input | Cron equivalent | Description |
|---|---|---|
| `weekly` or `--schedule weekly` | Every Sunday 3:00 AM local | Default weekly consolidation |
| `daily` | Every day 3:00 AM local | For high-volume projects |
| `biweekly` | Every other Sunday 3:00 AM local | Lower frequency option |
| Custom (e.g., `"every Monday 9am"`) | Pass verbatim to `/schedule` | Let Claude Code resolve it |

### Step S2: Create the routine

Use Claude Code's `/schedule` command to create a cloud routine. The routine runs
`/mem0:dream --auto` on the specified schedule against the current repository:

```
/schedule <frequency> /mem0:dream --auto
```

For example:
- `/schedule weekly /mem0:dream --auto` — runs every week
- `/schedule daily at 3am /mem0:dream --auto` — runs every day at 3 AM
- `/schedule every Monday 9am /mem0:dream --auto` — runs every Monday at 9 AM

The `/schedule` command handles all the cloud infrastructure: repository cloning,
environment setup, and cron scheduling. The routine runs as a full Claude Code
cloud session with access to the mem0 MCP tools.

### Step S3: Confirm to user

After the routine is created, print:

```
Dream scheduled: <frequency>
Routine name: mem0-dream-<project_id>
Next run: <next scheduled time>

Manage at: https://claude.ai/code/routines
Edit: /schedule list → /schedule update
Cancel: /schedule list → delete the routine
```

### Managing scheduled dreams

| Action | Command |
|---|---|
| List all routines | `/schedule list` |
| Run dream now | `/schedule run` (select the dream routine) |
| Change frequency | `/schedule update` (select the dream routine) |
| Pause | Toggle off at claude.ai/code/routines |
| Delete | Delete at claude.ai/code/routines or `/schedule update` |

### Fallback for non-cloud users

If `/schedule` is unavailable (API key auth, no claude.ai subscription), fall back
to local options:

1. **macOS launchd plist** — generate and install:
   ```bash
   cat > ~/Library/LaunchAgents/com.mem0.dream.plist << 'PLIST'
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0">
   <dict>
     <key>Label</key><string>com.mem0.dream</string>
     <key>ProgramArguments</key>
     <array>
       <string>claude</string>
       <string>-p</string>
       <string>/mem0:dream --auto</string>
       <string>--allowedTools</string>
       <string>mcp__mem0__*</string>
     </array>
     <key>StartCalendarInterval</key>
     <dict>
       <key>Weekday</key><integer>0</integer>
       <key>Hour</key><integer>3</integer>
       <key>Minute</key><integer>0</integer>
     </dict>
     <key>StandardOutPath</key><string>/tmp/mem0-dream.log</string>
     <key>StandardErrorPath</key><string>/tmp/mem0-dream.err</string>
     <key>WorkingDirectory</key><string>PROJECT_DIR</string>
   </dict>
   </plist>
   PLIST
   launchctl load ~/Library/LaunchAgents/com.mem0.dream.plist
   ```
   Replace `PROJECT_DIR` with the actual project path.

2. **Linux cron** — add entry:
   ```bash
   (crontab -l 2>/dev/null; echo "0 3 * * 0 cd PROJECT_DIR && claude -p '/mem0:dream --auto' >> /tmp/mem0-dream.log 2>&1") | crontab -
   ```

Print which method was used and how to verify:
```
Dream scheduled (local: launchd/cron): weekly Sundays 3am
Verify: launchctl list | grep mem0   # macOS
        crontab -l | grep mem0       # Linux
```
