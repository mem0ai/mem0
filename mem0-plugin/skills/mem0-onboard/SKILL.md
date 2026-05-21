---
name: mem0-onboard
description: >
  Post-install onboarding wizard for the mem0 plugin.
  Detects CLAUDE.md, AGENTS.md, .cursorrules, .windsurfrules, mem0.md
  and offers to import them. Installs coding categories. Shows active identity.
  TRIGGER: user runs /mem0:onboard, or mentions "setup mem0", "configure mem0 plugin".
---

# Mem0 Onboarding Wizard

Run this wizard to set up the mem0 plugin for the current project. Complete in ~30 seconds.

## Step 1: Verify API key

Check if `MEM0_API_KEY` is set in the current environment:

```bash
echo "${MEM0_API_KEY:+SET}" || echo "NOT_SET"
```

- If **NOT set**:
  1. Ask the user: "No MEM0_API_KEY found. Do you have one, or need to create one?"
  2. If they need one, provide two options:
     - **Browser**: Go to https://app.mem0.ai/dashboard/api-keys and copy the key
     - **CLI**: Run `pip install mem0-cli && mem0 init --agent --json` to mint a key without email
  3. Once they have the key, tell them to run: `export MEM0_API_KEY="m0-..."` in their terminal, then restart this Claude Code session (the env var must be set before Claude Code starts).
  4. **STOP here.** Do not proceed until the key is confirmed set.
- If **SET**: Proceed to Step 2.

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

If yes, run the script directly (no external dependencies required — uses stdlib only).

The script lives at `scripts/setup_coding_categories.py` relative to the plugin root. Use the appropriate plugin root variable for the current platform:
- Claude Code: `${CLAUDE_PLUGIN_ROOT}`
- Codex: `${CODEX_PLUGIN_ROOT}`
- Cursor: `${CURSOR_PLUGIN_ROOT}`

```bash
python3 "<PLUGIN_ROOT>/scripts/setup_coding_categories.py" --apply
```

If the script reports an error, show the error message and suggest checking the API key.

## Step 5: Mark project as onboarded

Create a marker file so SessionStart won't re-trigger onboarding next session:

```bash
mkdir -p ~/.mem0 && touch ~/.mem0/.onboarded_<active_project_id>
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
