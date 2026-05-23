---
name: mem0-export
description: >
  Export all project memories to a portable Markdown file.
  TRIGGER: user runs /mem0:export, or asks "export memories", "backup memories",
  "download my memories", "save memories to file".
---

# Mem0 Export

Export all memories for the current project to a portable Markdown file.

## Execution

### Step 1: Resolve identity

Determine the active identity:
- `user_id` from `MEM0_USER_ID` env var, else `$USER`, else `"default"`
- `project_id` (used as `app_id`) from `MEM0_PROJECT_ID` env var, or via the project resolver

### Step 2: Fetch all memories

Call `get_memories` with:
- `user_id=<active_user_id>`
- `app_id=<active_project_id>`
- `page_size=200`

If the response is paginated (i.e. the result contains a `next` cursor or the count equals `page_size`), continue fetching pages until all memories are retrieved.

### Step 3: Format each memory as a YAML-frontmatter block

For each memory record, produce a block in this exact format:

```
---
id: <memory.id>
created_at: <memory.created_at>
type: <memory.metadata.type or "">
confidence: <memory.metadata.confidence or "">
branch: <memory.metadata.branch or "">
files: <memory.metadata.files joined with ", " or "">
categories: <memory.categories joined with ", " or "">
---
<memory.memory or memory content string>

```

Notes:
- The `---` delimiters must be on their own lines with no extra whitespace.
- `files` and `categories` are written as comma-separated values on a single line.
- Leave a blank line after the content before the next `---` (for readability).
- If a field is missing or null, write an empty string (not "null").

### Step 4: Write the export file

Determine the output filename:

```
mem0-export-<project_id>-<YYYY-MM-DD>.md
```

Where `<YYYY-MM-DD>` is today's date in UTC.

Write all formatted blocks to this file using the Write tool (or equivalent). The file is written to the current working directory.

### Step 5: Print summary

```
Exported <N> memories to <filename>
```

Where `<N>` is the total number of memory blocks written.

## Error Handling

- If `get_memories` returns an error or zero memories, print:
  ```
  No memories found for project <project_id>. Nothing exported.
  ```
- If the write fails, report the error to the user.
