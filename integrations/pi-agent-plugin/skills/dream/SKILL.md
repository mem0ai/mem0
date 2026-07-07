---
name: dream
description: Consolidates stored memories by merging duplicates, resolving contradictions, and pruning stale entries. Use when memory count is high, search results feel noisy or repetitive, or periodic cleanup is needed to maintain memory quality.
---

# Dream — Memory Consolidation

This skill performs a memory consolidation pass: it fetches all memories, identifies near-duplicates, flags contradictions, and prunes stale entries. All proposed changes are shown as a diff for user approval before anything is modified.

**IMPORTANT: Execute steps strictly in order (1 -> 2 -> 3 -> 4 -> 5). Each step depends on the previous one. Do NOT run steps in parallel or skip ahead.**

## Step 1: Fetch ALL Memories

Use `mem0_memory` tool with `action="get_all"` to retrieve every memory.

If zero memories are found, print:

```
No memories found. Nothing to consolidate.
```

...and stop.

## Step 2: Analyze — Find Issues

Work entirely in-memory; do not modify anything yet.

Group memories by category. For each group, identify the following:

### 2a. Near-duplicate pairs (merge candidates)

Two memories are near-duplicates when they express the same fact but phrased differently (e.g., "Prefers morning meetings" and "Likes scheduling meetings early").

Heuristics — two memories are near-duplicates if **all** of these hold:
- If >60% of significant nouns/keywords overlap, treat as near-duplicate.
- Same category.
- Neither memory is pinned (content does not start with `[PINNED]`).

For each qualifying pair, draft a merged version that is more complete than either original.

### 2b. Contradictions

Two memories contradict when they assert opposing facts about the same topic (e.g., "Prefers cats" vs. "Allergic to cats, prefers dogs").

Identify the likely winner: the more recent memory wins. Store both IDs and their content for user review.

### 2c. Prune candidates

A memory is a prune candidate when **any** of the following is true:

1. It is older than 180 days AND has not been accessed recently.
2. Its content is extremely vague (fewer than 5 meaningful words).

**Always skip memories where content starts with `[PINNED]`**, regardless of age.

## Step 3: Print Diff Report

Print a structured diff before making any changes:

```
## dream — consolidation report

Merges (<N>):
  [mem0:<id1>] + [mem0:<id2>] -> "<merged content, 100 chars>"

Conflicts (<N>):
  [mem0:<idA>] vs [mem0:<idB>] — "<topic>" [A/B/skip]

Prune (<N>):
  [mem0:<id>] — <category>, <age>d old

Proposed: <N> merges, <N> prunes, <N> conflicts. Apply? [Y/n]
```

If there are zero total proposals, print:

```
Dream complete. No duplicate, contradictory, or stale memories found.
```

...and stop.

## Step 4: Wait for User Input and Apply

### 4a. Contradictions

For each conflict pair, wait for the user to choose A, B, or skip.

### 4b. Final confirmation

After all conflict resolutions are collected, prompt: `Apply? [Y/n]`

If the user declines, print `Cancelled. No changes made.` and stop.

If confirmed, apply all changes:

**Merges:** Delete both originals, add the merged version using `mem0_memory` with `action="add"`.

**Contradictions (resolved):** Delete the loser using `mem0_memory` with `action="delete"`.

**Prunes:** Delete each using `mem0_memory` with `action="delete"`.

## Step 5: Print Summary

```
Dream complete — merged: <N>, pruned: <N>, conflicts resolved: <N>, skipped: <N>
```

## Auto mode

When invoked with `--auto` (e.g., `/mem0-dream --auto`), run non-interactively:

- **Merges**: applied automatically.
- **Prunes**: applied automatically.
- **Contradictions**: skipped — they require human judgment.

Print a compact summary:
```
[mem0-dream --auto] merged=<N> pruned=<N> conflicts_skipped=<N>
```

## See also

- `/mem0-forget` — targeted deletion of specific memories
- `/mem0-status` — quick health check
