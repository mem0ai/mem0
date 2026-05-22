---
name: mem0-import-tools
description: >
  Import memories from competing AI tool configuration files into mem0.
  Supports Cursor (.cursorrules), GitHub Copilot (.github/copilot-instructions.md),
  Cline (memory-bank/), and Continue (.continue/rules.md).
  TRIGGER: user runs /mem0:import-tools, or asks "import from cursor",
  "import cursorrules", "import from cline", "import from copilot",
  "import from continue", "migrate from cursor", "migrate memories".
---

# Mem0 Import from Competing Tools

Import configuration and memory files from other AI coding tools into mem0.

## Supported Tools

| Tool | Default file/directory |
|------|----------------------|
| Cursor | `.cursorrules` |
| GitHub Copilot | `.github/copilot-instructions.md` |
| Cline | `memory-bank/` (directory of `.md` files) |
| Continue | `.continue/rules.md` |

## Execution

### Step 1: Detect which tool files exist

Check for the presence of each tool's file/directory in the current working directory:

```bash
# Check each location
test -f .cursorrules && echo "cursor: .cursorrules"
test -f .github/copilot-instructions.md && echo "copilot: .github/copilot-instructions.md"
test -d memory-bank/ && echo "cline: memory-bank/"
test -f .continue/rules.md && echo "continue: .continue/rules.md"
```

### Step 2: Report findings and ask user

List all found files to the user. For example:

```
Found the following tool configuration files:
  [1] Cursor rules: .cursorrules
  [2] Cline memory bank: memory-bank/

Which would you like to import? (enter numbers, comma-separated, or "all"):
```

If no files are found, print:
```
No competing tool configuration files found in the current directory.
Checked: .cursorrules, .github/copilot-instructions.md, memory-bank/, .continue/rules.md
```
and stop.

### Step 3: Run the import script for each selected tool

Determine the plugin root. Use the appropriate variable for the current platform:
- Claude Code: `${CLAUDE_PLUGIN_ROOT}`
- Codex: `${CODEX_PLUGIN_ROOT}`
- Cursor: `${CURSOR_PLUGIN_ROOT}`

For each tool the user selected, run the corresponding sub-command:

**Cursor (.cursorrules):**
```bash
python3 "<PLUGIN_ROOT>/scripts/import_competing_tools.py" cursorrules --path .cursorrules
```

**GitHub Copilot:**
```bash
python3 "<PLUGIN_ROOT>/scripts/import_competing_tools.py" copilot --path .github/copilot-instructions.md
```

**Cline:**
```bash
python3 "<PLUGIN_ROOT>/scripts/import_competing_tools.py" cline --path memory-bank/
```

**Continue:**
```bash
python3 "<PLUGIN_ROOT>/scripts/import_competing_tools.py" continue --path .continue/rules.md
```

### Step 4: Report results

After each script runs, echo its output to the user. Then print a combined summary:

```
Import complete.
  Cursor:  <N> memories
  Copilot: <N> memories
  Total:   <N> memories imported into project <project_id>
```

Adjust the summary to reflect only the tools that were actually imported.

## Notes

- Memories are imported with `infer=False` — no AI inference is applied, content is stored as-is.
- Each section or file becomes a separate memory tagged with `metadata.source=<tool>-import` and `metadata.type=project_profile`.
- Sections shorter than 50 characters are automatically skipped (too short to be useful).
- Content longer than 10,000 characters is automatically truncated per chunk.
- You can re-run this skill safely — duplicate content will be caught by mem0's deduplication.
