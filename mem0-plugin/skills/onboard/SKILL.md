---
name: onboard
description: Sets up mem0 for a new project including API key configuration, MCP authentication, project file import, and coding categories. Use on first run in a new project, when API key needs updating, or to re-run initial setup after configuration changes.
---

# Mem0 Onboarding Wizard

Run this wizard to set up the mem0 plugin for the current project. Complete in ~60 seconds.

## Step 0: Ensure mem0ai SDK is installed

The plugin installs the `mem0ai` Python SDK automatically on session start via a venv in `${CLAUDE_PLUGIN_DATA}/venv`. If Step 5 (categories) fails with an import error, run:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/ensure_deps.sh"
```

This is silent and idempotent — safe to run anytime.

## Step 1: Set up API key

Check if `MEM0_API_KEY` is already set by running:

```bash
echo $MEM0_API_KEY
```

### If API key IS set (non-empty output)

Print: `- API key found.` and proceed to Step 2.

### If API key is NOT set (empty output)

Guide the user through API key setup. Show this message and walk them through it:

```
Step 1: Setting up API key.

- MEM0_API_KEY not found. Let's set it up.

  1. Get your API key from https://app.mem0.ai/dashboard/api-keys
     (or run: mem0 init --agent --json)

  2. Add to shell profile:
     echo 'export MEM0_API_KEY="m0-your-key-here"' >> ~/.zshrc
     source ~/.zshrc

  3. Verify:
     echo $MEM0_API_KEY
     # Should print your key
```

After the user confirms they've set the key, verify it by running `echo $MEM0_API_KEY`. If still empty, repeat the instructions. If set, proceed to Step 2.

## Step 2: MCP OAuth login

Now authenticate the MCP server connection. Tell the user:

```
Step 2: MCP OAuth login.

  1. Type /mcp in Claude Code
  2. A browser window will open for authentication at mcp.mem0.ai
  3. Log in with your mem0 account
  4. Return here after authenticating in your browser
```

After the user completes OAuth, verify MCP tools are available using ToolSearch with query `"mem0 search_memories"`. The exact tool name varies by install method (may be `mcp__mem0__search_memories` or `mcp__plugin_mem0_mem0__search_memories`).

- If MCP tools found: Print `- MCP connected.` and proceed to Step 3.
- If NOT found: Troubleshoot before giving up:
  1. Check plugin is installed: run `/plugins` and confirm `mem0` appears
  2. Ask if the browser auth completed successfully
  3. Look for `mcp.mem0.ai` in the MCP server list via `/mcp`
  4. If all checks fail: "Restart Claude Code and run `/mem0:onboard` again."
  **STOP here** — do not proceed without MCP tools.

## Step 3: Verify connectivity and show identity

Call `search_memories` with `query="project setup"`, `user_id=<active_user_id>`, `filters={"AND": [{"user_id": "<active_user_id>"}, {"app_id": "<active_project_id>"}]}`, `limit=1` to verify connectivity.

Print:
```
- Connected
  user:    <user_id>
  project: <project_id>
  branch:  <branch>
```

If the search fails, troubleshoot the API key and MCP connection.

## Step 4: Detect and import project files

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
- The response contains `event_id` (writes are async). Do not block on each — continue importing. The summary reflects files submitted, not confirmed processed.

## Step 5: Install coding categories

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

## Step 6: Mark project as onboarded

```bash
_SAFE_PID=$(printf '%s' "<active_project_id>" | tr '/:' '--')
mkdir -p ~/.mem0 && touch ~/.mem0/.onboarded_${_SAFE_PID}
```

This is silent — no user-facing output needed.

## Step 7: Summary

Print a summary:
```
- Onboarding complete.
  user_id:    <user_id>
  project_id: <project_id> (app_id)
  imported:   <N> files
  categories: <installed or skipped>

Memory is now active for this project. Start working — mem0 will
automatically search relevant context and capture learnings.

Run /mem0:tour to see what mem0 already knows about this project.
```
