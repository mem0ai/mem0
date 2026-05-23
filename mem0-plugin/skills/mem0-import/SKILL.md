---
name: mem0-import
description: Import memories from an export file or competing tools into this project
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

Determine the plugin root. Use the appropriate variable for the current platform:
- Claude Code: `${CLAUDE_PLUGIN_ROOT}`
- Codex: `${CODEX_PLUGIN_ROOT}`
- Cursor: `${CURSOR_PLUGIN_ROOT}`

Run the parser script to extract memory records as JSON:

```bash
python3 "<PLUGIN_ROOT>/scripts/parse_export_file.py" "<path-to-export-file>"
```

This outputs a JSON array where each element has:
- `id` — original memory ID (for reference only; a new ID will be assigned on import)
- `type` — metadata type
- `confidence` — metadata confidence value
- `branch` — metadata branch
- `files` — list of associated files
- `categories` — list of categories
- `content` — the memory text

If the script fails or outputs `[]`, print:
```
Failed to parse <filename> or file contains no valid memory blocks.
```
and stop.

### Step 3: Resolve identity

Determine the active identity:
- `user_id` from `MEM0_USER_ID` env var, else `$USER`, else `"default"`
- `project_id` (used as `app_id`) from `MEM0_PROJECT_ID` env var, or via the project resolver

### Step 4: Import each memory

For each record in the parsed JSON array, call `add_memory` with:

- `messages=[{"role": "user", "content": "<record.content>"}]`
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
- Skip records where `content` is empty (the parser already filters these, but be defensive).
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

### T3: Run import

For each selected tool:
```bash
python3 "<PLUGIN_ROOT>/scripts/import_competing_tools.py" <tool> --path <file>
```

Tools: `cursorrules`, `copilot`, `cline`, `continue`.

### T4: Report

```
Import complete.
  Cursor:  <N> memories
  Copilot: <N> memories
  Total:   <N> memories imported into project <project_id>
```

Notes: `infer=False`, tagged `metadata.source=<tool>-import`, sections <50 chars
skipped, chunks >10k chars truncated, safe to re-run (deduplication handles it).

---

## Importing Claude Code's native MEMORY.md

When invoked with a path to Claude Code's native `MEMORY.md` file (typically
`~/.claude/projects/<proj-key>/memory/MEMORY.md`), or when `on_session_start.sh`
detects native auto-memory and the user chooses to import:

1. Read the file. It contains newline-separated memory entries (one fact per line,
   sometimes with `- ` bullet prefix).
2. Split by non-empty lines. Each line becomes one memory.
3. Skip lines shorter than 20 characters or lines that are just headers (`#`).
4. For each line, call `add_memory` with:
   - `messages=[{"role": "user", "content": "<line>"}]`
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

- If the parser script is not found at `<PLUGIN_ROOT>/scripts/parse_export_file.py`, print an error and stop.
- If `add_memory` calls fail consistently (e.g. auth error), report the issue and stop early.
