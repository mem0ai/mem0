---
name: "mem0:onboard"
description: Sets up mem0 for a new project including API key configuration, MCP authentication, project file import, and coding categories. Use on first run in a new project, when API key needs updating, or to re-run initial setup after configuration changes.
---

# Mem0 Onboarding Wizard

Run this wizard to set up the mem0 plugin for the current project. Complete in ~60 seconds.

**IMPORTANT: Execute steps strictly in order (0 → 1 → 2 → 3 → 4 → 5 → 6). Each step depends on the previous one. Do NOT run steps in parallel or skip ahead. Complete one step fully before starting the next.**

## Step 0: Skip dependency install

The plugin lists `mem0ai` as a declared dependency — no install step is needed. Proceed directly to Step 1.

## Step 1: Set up API key

Check if the API key is available:

```bash
[ -n "${MEM0_API_KEY:-}" ] && echo "SET" || echo "NOT_SET"
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

     Option A — Shell profile:
       echo 'export MEM0_API_KEY="m0-your-key-here"' >> ~/.zshrc
       source ~/.zshrc

     Option B — OpenCode environment config:
       Add MEM0_API_KEY to your OpenCode environment settings
       so it is available in all sessions.

  3. Verify:
     [ -n "${MEM0_API_KEY:-}" ] && echo "SET" || echo "NOT_SET"
```

After the user confirms, re-run the verify command. If NOT_SET, repeat. If SET, proceed to Step 2.

## Step 2: MCP server connection

First, check if MCP tools are already available using ToolSearch with query `"mem0 search_memories"`. The exact tool name varies by install method (may be `mcp__mem0__search_memories` or `mcp__plugin_mem0_mem0__search_memories`).

**If MCP tools ARE found:** Print `- MCP already connected.` and proceed to Step 3.

**If MCP tools are NOT found:**

The MCP server authenticates using the `MEM0_API_KEY` set in Step 1. No OAuth or browser login is needed.

1. Verify the API key is set (re-run the Step 1 check)
2. Check the plugin is installed and the MCP server for mem0 is listed in OpenCode's MCP configuration
3. If the server shows an error, ask the user to restart OpenCode and run `/mem0:onboard` again
4. If all checks pass but tools are still missing: "Restart OpenCode and run `/mem0:onboard` again."

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

Check for common project context files in the working directory root. Read any that exist and store their key facts as memories using `add_memory`.

### 4a: Detect project files

```bash
for f in CLAUDE.md AGENTS.md .cursorrules .windsurfrules mem0.md .mem0.md; do
  [ -f "$f" ] && echo "FOUND: $f ($(wc -c < "$f") bytes)"
done || true
```

If no files found, print `- No project files found. Skipping import.` and proceed to Step 5.

### 4b: Read and import via MCP

For each file found in 4a:

1. Read the file contents with the Read tool.
2. Extract the key facts, conventions, and decisions documented in the file. Do not import the entire file verbatim — summarize meaningful chunks.
3. Call `add_memory` for each meaningful chunk with:
   - `data`: the extracted fact or convention
   - `user_id`: the active user id
   - `app_id`: the active project id
   - `metadata`: `{"source": "<filename>", "type": "project_context"}`

If a file is very large (over 4000 bytes), split it into logical sections (one `add_memory` call per section).

### 4c: Report to user

After processing all files, print a user-friendly summary:

```
- Importing project files into mem0... done.
  <N> file(s) read, <M> memories stored.
  These are available as context for future sessions.
```

If `add_memory` calls fail, print:
```
- Project file import failed. Check API key and MCP connection, then retry with: /mem0:onboard
```

## Step 5: Verify coding categories

Coding categories are now configured automatically in the background when the plugin starts. This step only verifies they are set up.

Check if the categories are already configured by searching for a project_profile memory:

Call `search_memories` with `query="coding categories project profile"`, `filters={"AND": [{"user_id": "<active_user_id>"}, {"app_id": "<active_project_id>"}]}`, `top_k=1`.

If a project_profile memory is found, print:
```
- Coding categories already configured (17 categories, auto-installed).
```

If no project_profile memory is found, store one as a fallback. Call `add_memory` once with:

- `data`: a plain-text description of the project profile and the list of active coding categories:
  ```
  Project profile for <project_id>.
  Active coding categories: architecture_decisions, api_design, data_models,
  algorithms, dependencies, environment_setup, testing_strategy, debugging_notes,
  performance, security, deployment, code_conventions, error_handling,
  refactoring_history, integrations, onboarding, project_meta.
  ```
- `user_id`: the active user id
- `app_id`: the active project id
- `metadata`: `{"type": "project_profile", "source": "onboard"}`

After the `add_memory` call succeeds, print:
```
- Coding categories installed (17 categories).
```

## Step 6: Summary

Print a summary:
```
- Onboarding complete.
  user_id:    <user_id>
  project_id: <project_id> (app_id)
  files:      <N> found, <M> memories stored
  categories: <N installed | already installed | skipped by user>

Memory is now active for this project. Start working — mem0 will
automatically search relevant context and capture learnings.

Run /mem0:tour to see what mem0 already knows about this project.
```

## Output formatting

IMPORTANT: Do NOT use markdown in your output. OpenCode TUI renders text verbatim — markdown like **bold**, ## headers, and | table | syntax appears as raw characters. Use plain text with indentation for structure. Use dashes for lists. Use spaces to align columns instead of markdown tables.
