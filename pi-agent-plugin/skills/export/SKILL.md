---
name: export
description: Exports all project memories to a portable Markdown file for backup or migration. Use when backing up memories, migrating to another project, sharing memory state, or archiving before cleanup.
---

# Export

Export all memories for the current project to a portable Markdown file.

## Execution

### Step 1: Fetch all memories

Use `mem0_memory` tool with `action="get_all"` to fetch all memories.

If zero memories found:
```
No memories found. Nothing to export.
```
...and stop.

### Step 2: Format each memory as a YAML-frontmatter block

For each memory record, produce a block in this format:

```
---
id: <memory.id>
created_at: <memory.created_at>
categories: <memory.categories joined with ", " or "">
---
<memory content text>

```

Notes:
- The `---` delimiters must be on their own lines.
- Leave a blank line after the content before the next `---`.
- If a field is missing, write an empty string (not "null").

### Step 3: Output

Determine the output filename:

```
mem0-export-<project_id>-<YYYY-MM-DD>.md
```

Present the formatted export content via `pi.sendMessage`. The user or agent can then write it to a file.

### Step 4: Print summary

```
Exported <N> memories to <filename>
```

## Error Handling

- If `get_all` returns an error, report it to the user.
- If zero memories, print the empty state and stop.
