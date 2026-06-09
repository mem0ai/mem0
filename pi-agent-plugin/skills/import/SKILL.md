---
name: import
description: Imports memories from an exported Markdown file or text input into the current project. Use when migrating from another project, restoring from backup, or setting up a new project with existing knowledge.
---

# Import

Import memories from a Mem0 export file or user-provided text into the current project.

## Execution

### Step 1: Determine the source

If the user provided a filename as an argument to `/mem0-import <filename>`, use that file.

If the user provided raw text or pasted memories, parse them directly.

If neither, ask: "Provide a filename or paste the memories you'd like to import."

### Step 2: Parse the source

**From an export file** (Markdown with YAML frontmatter blocks):

Parse each `---` delimited block. Extract:
- `id` — original memory ID (for reference only; a new ID will be assigned)
- `categories` — list of categories
- `content` — the memory text (everything between frontmatter and next block)

Skip blocks where content is empty.

**From raw text:**

Split by non-empty lines. Each line becomes one memory.
Skip lines shorter than 10 characters or lines that are just headers (`#`).

### Step 3: Import each memory

For each record, use `mem0_memory` tool with:
- `action="add"`
- `content="<record.content>"`

Notes:
- Do NOT pass the original `id` — the platform assigns a new ID.
- Continue importing even if individual records fail; track the count of successes.

### Step 4: Print results

```
Imported <N> memories into project <project_id>
```

If any failed:
```
Imported <N>/<total> memories (<failed> failed)
```

## Error Handling

- If the file cannot be read, report the error and stop.
- If `add` calls fail consistently (e.g., auth error), report the issue and stop early.
