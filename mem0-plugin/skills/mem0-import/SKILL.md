---
name: mem0-import
description: >
  Import memories from a mem0 export file back into the current project.
  Reads a YAML-frontmatter Markdown file produced by /mem0:export and
  adds each memory block to mem0.
  TRIGGER: user runs /mem0:import, or asks "import memories", "restore memories",
  "load memories from file", "reimport backup".
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

## Error Handling

- If the parser script is not found at `<PLUGIN_ROOT>/scripts/parse_export_file.py`, print an error and stop.
- If `add_memory` calls fail consistently (e.g. auth error), report the issue and stop early.
