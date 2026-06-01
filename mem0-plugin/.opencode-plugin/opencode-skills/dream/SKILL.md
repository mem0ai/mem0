---
name: "mem0:dream"
description: Consolidates stored memories by merging duplicates, resolving contradictions, and pruning stale entries. Use when memory count is high, search results feel noisy or repetitive, or periodic cleanup is needed to maintain memory quality.
---

# Mem0 Dream — Memory Consolidation

This skill performs a memory consolidation pass: it fetches all project memories,
identifies near-duplicates, flags contradictions, and prunes stale entries based on
configured retention policies. All proposed changes are shown as a diff for user
approval before anything is modified.

**IMPORTANT: Execute steps strictly in order (1 → 2 → 3 → 4 → 5 → 6). Each step depends on the previous one. Do NOT run steps in parallel or skip ahead.**

## Step 1: Load Retention Policies

Check for a project config file in the project root (current working directory):

1. Look for `.mem0.json` first. If it exists, parse it as JSON and read the
   `retention` field (a dict of `category → days | null`).
2. If `.mem0.json` is not present, look for `.mem0.md`. If it exists, scan it
   for a `retention:` section or YAML front matter with retention settings and
   parse what you find.
3. If neither file exists, skip config loading entirely.

If no config is found or the config contains no retention settings, fall back to
these built-in defaults:

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
    filters={"AND": [{"user_id": "<active_user_id>"}, {"app_id": "<active_project_id>"}]},
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

Heuristics — two memories are near-duplicates if **all** of these hold:
- Similarity threshold: estimated cosine similarity > 0.9 (use noun/keyword overlap as proxy — if >60% of significant nouns overlap, treat as >0.9 similarity).
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

## Step 4: Print Diff Report

Print a structured diff to the terminal before making any changes. Use exactly
this format:

```
## dream — consolidation report

Merges (<N>):
  [mem0:<id1>] + [mem0:<id2>] → "<merged content, 100 chars>"

Conflicts (<N>):
  [mem0:<idA>] vs [mem0:<idB>] — "<topic>" [A/B/skip]

Prune (<N>):
  [mem0:<id>] — <type>, <age>d old

Proposed: <N> merges, <N> prunes, <N> conflicts. Apply? [Y/n]
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
   - `text="<merged content>"`
   - `user_id=<active_user_id>`
   - `app_id=<active_project_id>` (top-level, not in metadata)
   - `metadata={"type": "<original type>", "branch": "<active_branch>", "confidence": <higher of the two original scores>, "source": "mem0-dream"}`
   - `infer=False`

#### Contradictions (resolved)

For each resolved conflict where the user chose A or B:
- Delete the loser (the non-chosen memory): `delete_memory(memory_id=<loser_id>)`

Contradictions where the user chose `skip` are left untouched.

#### Prunes

For each prune candidate:
- `delete_memory(<memory_id>)`

---

## Step 6: Print Summary

After all changes are applied, print:

```
Dream complete — merged: <N>, pruned: <N>, conflicts resolved: <N>, skipped: <N>
```

---

## Auto mode

When invoked with `--auto` (e.g., `/mem0:dream --auto`), run non-interactively:

- **Merges**: applied automatically (no contradiction, both are compatible).
- **Prunes**: applied automatically (age/confidence-based, no ambiguity).
- **Contradictions**: skipped — they require human judgment.

### Concurrency guard

Before doing any work, check for a lock file at `/tmp/mem0_dream_auto.lock`:
- If the lock file exists and is less than 10 minutes old, print `[mem0-dream --auto] Another run in progress — skipping.` and stop.
- Otherwise, create the lock file (write the current timestamp). Delete it when done (in all exit paths).

### Execution

In auto mode:
1. Load policies and fetch memories (Steps 1–3) as normal.
2. Apply merges and prunes silently without printing the diff or prompting.
3. Print a compact summary:
   ```
   [mem0-dream --auto] project=<id>  merged=<N>  pruned=<N>  conflicts_skipped=<N>
   ```
4. If contradictions were detected but skipped, check if a `mem0-dream-auto` reminder already exists before storing one:
   - Search for existing reminders: `search_memories(query="mem0-dream contradictions manual review", filters={"AND": [{"user_id": "<active_user_id>"}, {"app_id": "<active_project_id>"}, {"metadata": {"source": "mem0-dream-auto"}}]}, top_k=1)`
   - If a result exists with similarity > 0.9, skip storing the reminder (one already exists).
   - If no match, store the reminder:
   ```python
   add_memory(
       text="mem0-dream detected <N> contradiction(s) requiring manual review. Run /mem0:dream to resolve them interactively.",
       user_id="<active_user_id>",
       app_id="<active_project_id>",
       metadata={"type": "task_learning", "source": "mem0-dream-auto", "branch": "<active_branch>"},
       infer=False,
   )
   ```

## See also

- `/mem0:forget` — targeted deletion of specific memories (search + confirm + delete)
- `/mem0:health --deep` — quick quality scan without applying changes

## Output formatting

IMPORTANT: Do NOT use markdown in your output. OpenCode TUI renders text verbatim — markdown like **bold**, ## headers, and | table | syntax appears as raw characters. Use plain text with indentation for structure. Use dashes for lists. Use spaces to align columns instead of markdown tables.
