---
name: mem0-onboard
description: >
  Set up mem0 for this project — detect config files, install categories, verify identity.
  TRIGGER: user runs /mem0:onboard, or mentions "setup mem0", "configure mem0 plugin".
---

# Mem0 Onboarding Wizard

Run this wizard to set up the mem0 plugin for the current project. Complete in ~30 seconds.

## Step 0: Ensure mem0ai SDK is installed

The plugin installs the `mem0ai` Python SDK automatically on session start via a venv in `${CLAUDE_PLUGIN_DATA}/venv`. If Step 4 (categories) fails with an import error, run:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/ensure_deps.sh"
```

This is silent and idempotent — safe to run anytime.

## Step 1: Verify API key and MCP connection

Check that mem0 MCP tools are available. Use ToolSearch with query `"mem0 search_memories"` — the exact tool name varies by install method (may be `mcp__mem0__search_memories` or `mcp__plugin_mem0_mem0__search_memories`).

- If **any mem0 search tool found**: Proceed to Step 2. The API key is working.
- If **NOT found**: The MCP server failed to connect. Tell the user:
  1. "MCP server not connected. Make sure `MEM0_API_KEY` is exported in your shell."
  2. Show: `export MEM0_API_KEY="m0-your-key-here"` then restart Claude Code.
  3. If they need a key: https://app.mem0.ai/dashboard/api-keys or `mem0 init --agent --json`
  4. **STOP here.** Do not proceed — all other steps need MCP tools.

## Step 2: Show identity

Report the active identity to the user:
- Call `search_memories` with `query="project setup"`, `user_id=<active_user_id>`, `filters={"AND": [{"user_id": "<active_user_id>"}, {"app_id": "<active_project_id>"}]}`, `limit=1` to verify connectivity.
- Print: `Connected. user=<user_id>, project=<project_id>, branch=<branch>`
- If the search fails, troubleshoot the API key.

## Step 3: Detect and import project files

Check for these files in the project root:
1. `CLAUDE.md`
2. `AGENTS.md`
3. `.cursorrules`
4. `.windsurfrules`
5. `mem0.md`

For each file found, ask the user: "Found `<filename>` (<size> bytes). Import into mem0? [Y/n]"

If user says yes (or default):
- Read the file content
- Call `add_memory` with:
  - `messages=[{"role": "user", "content": "## Project Profile: <filename>\n\nProject: <project_id>\n\n<file_content>"}]`
  - `user_id=<active_user_id>`
  - `app_id=<active_project_id>`
  - `metadata={"type": "project_profile", "file": "<filename>", "source": "onboard", "branch": "<active_branch>"}`
  - `infer=False`

## Step 4: Install coding categories

Ask: "Install coding categories optimized for development workflows? [Y/n]"

If yes, run the setup script using the plugin's venv python:

```bash
VENV_PY="${CLAUDE_PLUGIN_DATA}/venv/bin/python3"
if [ -x "${VENV_PY}" ]; then
  "${VENV_PY}" "${CLAUDE_PLUGIN_ROOT}/scripts/setup_coding_categories.py" --apply
else
  python3 "${CLAUDE_PLUGIN_ROOT}/scripts/setup_coding_categories.py" --apply
fi
```

If the script fails with "mem0ai SDK not found", run the dependency installer first:
```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/ensure_deps.sh"
```
Then retry the categories script.

## Step 5: Mark project as onboarded

The marker file is already created by `on_session_start.sh` on first display of the onboard prompt. Touch it here for idempotency:

```bash
_SAFE_PID=$(printf '%s' "<active_project_id>" | tr '/:' '--')
mkdir -p ~/.mem0 && touch ~/.mem0/.onboarded_${_SAFE_PID}
```

This is silent — no user-facing output needed.

## Step 6: Summary

Print a summary:
```
Onboarding complete.
  user_id:    <user_id>
  project_id: <project_id> (app_id)
  imported:   <N> files
  categories: <installed or skipped>

Memory is now active for this project. Start working — mem0 will
automatically search relevant context and capture learnings.

Run /mem0:tour to see what mem0 already knows about this project.
```
