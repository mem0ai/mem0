---
name: onboard
description: Sets up mem0 for a new project including API key configuration, MCP authentication, project file import, and coding categories. Use on first run in a new project, when API key needs updating, or to re-run initial setup after configuration changes.
---

# Mem0 Onboarding Wizard

Run this wizard to set up the mem0 plugin for the current project. Complete in ~60 seconds.

**IMPORTANT: Execute steps strictly in order (0 → 1 → 2 → 3 → 4 → 5 → 6). Each step depends on the previous one. Do NOT run steps in parallel or skip ahead. Complete one step fully before starting the next.**

## Step 0: Ensure mem0ai SDK is installed

The plugin installs the `mem0ai` Python SDK automatically on session start via a venv in `${CLAUDE_PLUGIN_DATA}/venv`. If Step 5 (categories) fails with an import error, run:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/ensure_deps.sh"
```

This is silent and idempotent — safe to run anytime.

## Step 1: Set up API key

Check if the API key is available from any source:

```bash
[ -n "${MEM0_API_KEY:-${CLAUDE_PLUGIN_OPTION_API_KEY:-}}" ] && echo "SET" || echo "NOT_SET"
```

IMPORTANT: Never run `echo $MEM0_API_KEY` — that prints the secret in plaintext to the conversation log.

### If API key IS set (output is "SET")

Print: `- API key found.` and proceed to Step 2.

### If API key is NOT set (output is "NOT_SET")

Guide the user through API key setup. Show this message:

```
Step 1: Setting up API key.

- API key not found. Let's set it up.

  1. Get your API key from https://app.mem0.ai/dashboard/api-keys

  2. Choose ONE method:

     Option A — Plugin config (works on Desktop + CLI):
       Type:  ! claude plugin configure mem0
       Paste your API key when prompted.

     Option B — Shell profile (CLI only):
       echo 'export MEM0_API_KEY="m0-your-key-here"' >> ~/.zshrc
       source ~/.zshrc

  3. Verify:
     [ -n "${MEM0_API_KEY:-${CLAUDE_PLUGIN_OPTION_API_KEY:-}}" ] && echo "SET" || echo "NOT_SET"
```

After the user confirms, re-run the verify command. If NOT_SET, repeat. If SET, proceed to Step 2.

## Step 2: MCP server connection

First, check if MCP tools are already available using ToolSearch with query `"mem0 search_memories"`. The exact tool name varies by install method (may be `mcp__mem0__search_memories` or `mcp__plugin_mem0_mem0__search_memories`).

**If MCP tools ARE found:** Print `- MCP already connected.` and proceed to Step 3.

**If MCP tools are NOT found:** Guide the user through OAuth:

```
Step 2: MCP OAuth login.

  1. Type /mcp in Claude Code
  2. A browser window will open for authentication at mcp.mem0.ai
  3. Log in with your mem0 account
  4. Return here after authenticating in your browser
```

After the user completes OAuth, verify MCP tools again using ToolSearch.

- If MCP tools found: Print `- MCP connected.` and proceed to Step 3.
- If NOT found: Troubleshoot before giving up:
  1. Check plugin is installed: run `/plugins` and confirm `mem0` appears
  2. Ask if the browser auth completed successfully
  3. Look for `mcp.mem0.ai` in the MCP server list via `/mcp`
  4. If all checks fail: "Restart Claude Code and run `/mem0:onboard` again."
  **STOP here** — do not proceed without MCP tools.

## Step 3: Verify connectivity and show identity

Call `search_memories` with `query="project setup"`, `filters={"AND": [{"user_id": "<active_user_id>"}, {"app_id": "<active_project_id>"}]}`, `top_k=1` to verify connectivity.

Print:
```
- Connected
  user:    <user_id>
  project: <project_id>
  branch:  <branch>
```

If the search fails, troubleshoot the API key and MCP connection.

## Step 4: Import project files

Project files (CLAUDE.md, AGENTS.md, etc.) are automatically imported into mem0 when a session starts. This step verifies import status and triggers a re-import if needed.

### 4a: Detect project files

```bash
for f in CLAUDE.md AGENTS.md .cursorrules .windsurfrules mem0.md; do
  [ -f "$f" ] && echo "FOUND: $f ($(wc -c < "$f") bytes)"
done || true
```

If no files found, print `- No project files found. Skipping import.` and proceed to Step 5.

### 4b: Check and import

Run auto_import in foreground to check status and import if needed:

```bash
MEM0_DEBUG=1 MEM0_CWD="$PWD" python3 "${CLAUDE_PLUGIN_ROOT}/scripts/auto_import.py"
```

### 4c: Report to user

Parse the auto_import output and print a user-friendly summary:

- If output contains `Imported` lines:
  ```
  - Importing project files into mem0... done.
    <N> file(s) imported (<M> chunks). These are stored verbatim for future context.
  ```
- If output contains only `skipping` lines:
  ```
  - Project files already in mem0 (imported during session start). Verified server-side.
  ```
- If output contains `re-importing`:
  ```
  - Project files were missing from mem0. Re-imported successfully.
  ```
- If output contains errors or no files were processed:
  ```
  - Project file import failed. Check API key and retry with: /mem0:onboard
  ```

## Step 5: Install coding categories

The setup script is idempotent — it compares existing categories against the proposed set and skips the API call if they already match (tolerates order differences and extra API fields). Safe to re-run.

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

Parse the output:
- `"Categories already match -- skipping update."` → Print: `- Coding categories already installed. Skipped.`
- `"Done."` → Print: `- Coding categories installed (<N> categories).`
- Error → Print the error and suggest re-running `/mem0:onboard`.

If the script fails with "mem0ai SDK not found", run the dependency installer first:
```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/ensure_deps.sh"
```
Then retry the categories script.

## Step 6: Summary

Print a summary:
```
- Onboarding complete.
  user_id:    <user_id>
  project_id: <project_id> (app_id)
  files:      <N> found, <M> imported
  categories: <N installed | already installed | skipped by user>

Memory is now active for this project. Start working — mem0 will
automatically search relevant context and capture learnings.

Run /mem0:tour to see what mem0 already knows about this project.
```
