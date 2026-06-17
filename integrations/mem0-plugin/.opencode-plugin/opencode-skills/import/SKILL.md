---
name: import
description: Imports memories from an exported Markdown file or MEMORY.md into the current project. Use when migrating from another project, restoring from backup, importing Claude Code native MEMORY.md content, or setting up a new project with existing knowledge.
---

# Mem0 Import

Import memories from a mem0 export file into the current project.

## Execution

### Step 1: Determine the export file to import

If the user provided a filename as an argument to `/mem0:import <filename>`, use that file.

Otherwise, list `.md` files in the current directory whose names contain `mem0-export`:

```bash
ls -1 *.md 2>/dev/null | grep mem0-export || echo "No export files found"
```

If multiple files are found, ask the user which one to import. If none are found, print:
```
No mem0-export files found in the current directory.
Run /mem0:export first, or provide the filename: /mem0:import <path-to-file>
```

### Step 2: Parse the export file

Read the export file directly. It is a JSON file containing a top-level `memories` array. Each element has:
- `id` — original memory ID (for reference only; a new ID will be assigned on import)
- `type` — metadata type
- `confidence` — metadata confidence value
- `branch` — metadata branch
- `files` — list of associated files
- `categories` — list of categories
- `content` — the memory text

Parse the JSON in-memory (do not run any external script). If the file cannot be read or parsed, or if the `memories` array is missing or empty, print:
```
Failed to parse <filename> or file contains no valid memory blocks.
```
and stop.

### Step 3: Resolve identity

Determine the active identity:
- `user_id` from `MEM0_USER_ID` env var, else `$USER`, else `"default"`
- `project_id` (used as `app_id`) from `MEM0_PROJECT_ID` env var, or via the project resolver

### Step 4: Import each memory

For each record in the parsed JSON array, call `add_memory` (MCP tool) with:

- `text="<record.content>"`
- `user_id=<active_user_id>`
- `app_id=<active_project_id>`
- `metadata={`
  - `"type": "<record.type>"` (if non-empty)
  - `"confidence": "<record.confidence>"` (if non-empty)
  - `"branch": "<record.branch>"` (if non-empty)
  - `"files": <record.files>` (the list, if non-empty)
  - `"source": "import"`
  - `}`
- `infer=False`

Notes:
- Do NOT pass the original `id` — the platform assigns a new ID.
- Skip records where `content` is empty.
- Continue importing even if individual records fail; track the count of successes.

### Step 5: Print results

```
Imported <N> memories into project <project_id>
```

Where `<N>` is the number of successfully imported memories.

If any failed:
```
Imported <N>/<total> memories into project <project_id> (<failed> failed)
```

## Importing from competing AI tools (`--tools`)

When invoked with `--tools` (e.g., `/mem0:import --tools`), detect and import
from competing AI tool configuration files:

### Supported tools

| Tool | File/directory |
|------|---------------|
| Cursor | `.cursorrules` |
| GitHub Copilot | `.github/copilot-instructions.md` |
| Cline | `memory-bank/` (directory of `.md` files) |
| Continue | `.continue/rules.md` |

### T1: Detect

```bash
test -f .cursorrules && echo "cursor: .cursorrules"
test -f .github/copilot-instructions.md && echo "copilot: .github/copilot-instructions.md"
test -d memory-bank/ && echo "cline: memory-bank/"
test -f .continue/rules.md && echo "continue: .continue/rules.md"
```

### T2: Ask user

List found files, ask which to import (numbers, comma-separated, or "all").
If none found:
```
No competing tool configuration files found.
Checked: .cursorrules, .github/copilot-instructions.md, memory-bank/, .continue/rules.md
```

### T3: Import

For each selected tool, read the file(s) directly and split the content into logical
chunks to import as individual memories. No external scripts are used — all parsing
and importing is done via MCP tools.

Chunking rules per tool:

- **cursorrules / copilot / continue**: Read the file as plain text. Split on blank
  lines or section headers (`#`, `##`). Each non-empty chunk becomes one memory.
  Skip chunks shorter than 50 characters.

- **cline (memory-bank/)**: List all `.md` files in the directory. Read each file.
  Split each file on blank lines or headers. Each non-empty chunk becomes one memory.
  Skip chunks shorter than 50 characters.

For each chunk, call `add_memory` (MCP tool) with:
- `text="<chunk text>"`
- `user_id=<active_user_id>`
- `app_id=<active_project_id>`
- `metadata={"type": "task_learning", "source": "<tool>-import", "confidence": 0.8}`
- `infer=False`

Where `<tool>` is `cursorrules`, `copilot`, `cline`, or `continue`.

Notes: chunks longer than 10,000 characters are truncated before import. Safe to
re-run — deduplication handles repeated entries.

### T4: Report

```
Imported <N> memories into <project_id> (cursor: <N>, copilot: <N>)
```

---

## Importing Claude Code's native MEMORY.md

When invoked with a path to Claude Code's native `MEMORY.md` file (typically
`~/.claude/projects/<proj-key>/memory/MEMORY.md`), or when `on_session_start.sh`
detects native auto-memory and the user chooses to import:

1. Read the file directly. It contains newline-separated memory entries (one fact per
   line, sometimes with `- ` bullet prefix).
2. Split by non-empty lines. Each line becomes one memory.
3. Skip lines shorter than 20 characters or lines that are just headers (`#`).
4. For each line, call `add_memory` (MCP tool) with:
   - `text="<line>"`
   - `user_id=<active_user_id>`
   - `app_id=<active_project_id>`
   - `metadata={"type": "task_learning", "source": "memory-md-import", "confidence": 0.8}`
   - `infer=False`
5. Report: `Imported <N> memories from MEMORY.md into project <project_id>`
6. Suggest disabling native auto-memory:
   ```
   To avoid duplicate memory systems, add to ~/.claude/settings.json:
     "autoMemoryEnabled": false
   ```

This handles the cold-start gap when a user has been using Claude Code's native
memory and switches to mem0.

## Error Handling

- If `add_memory` calls fail consistently (e.g. auth error), report the issue and stop early.

## Output formatting

IMPORTANT: Do NOT use markdown in your output. OpenCode TUI renders text verbatim — markdown like **bold**, ## headers, and | table | syntax appears as raw characters. Use plain text with indentation for structure. Use dashes for lists. Use spaces to align columns instead of markdown tables.
