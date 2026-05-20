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

Check if `MEM0_API_KEY` is set:
- If NOT set: Tell the user to export it. Provide the link: `https://app.mem0.ai/dashboard/api-keys`
  - Also mention: `pip install mem0-cli && mem0 init --agent --json` can mint a key without email.
  - STOP here until the user confirms the key is set.
- If set: Proceed.

## Step 2: Show identity

Report the active identity to the user:
- Call `search_memories` with `query="project setup"`, `user_id=<active_user_id>`, `filters={"AND": [{"user_id": "<active_user_id>"}, {"metadata": {"project_id": "<active_project_id>"}}]}`, `limit=1` to verify connectivity.
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
  - `metadata={"type": "project_profile", "file": "<filename>", "project_id": "<active_project_id>", "source": "onboard"}`
  - `infer=False`

## Step 4: Install coding categories

Ask: "Install coding categories optimized for development workflows? [Y/n]"

If yes: Tell the user to run:
```bash
python3 mem0-plugin/scripts/setup_coding_categories.py --apply
```

If `mem0ai` Python SDK is not installed, suggest: `pip install mem0ai` first.

## Step 5: Summary

Print a summary:
```
Onboarding complete.
  user_id:    <user_id>
  project_id: <project_id>
  branch:     <branch>
  imported:   <N> files
  categories: <installed or skipped>

Memory is now active for this project. Start working — mem0 will
automatically search relevant context and capture learnings.

Run /mem0:tour to see what mem0 already knows about this project.
```
