---
name: "mem0:switch-project"
description: Overrides the auto-detected project scope to read and write memories under a different project ID, or enables global search to access all memories across all users and projects. Use when working across multiple projects, accessing memories from another repo, enabling team-wide memory access, or when auto-detection resolves to the wrong project.
---

# Mem0 Switch Project

Override the automatic project_id detection for the current directory, or enable global search mode.

## Usage

- `/mem0:switch-project <project-name>` — switch to a specific project scope
- `/mem0:switch-project --global` — enable global search (all memories, all users, all projects)
- `/mem0:switch-project --no-global` — disable global search and return to per-project scoping

## Execution

### If `--global` flag is provided:

1. Set `global_search: true` in `~/.mem0/settings.json` using the Bash tool:

   ```bash
   python3 -c "
   import json, os
   settings_file = os.path.expanduser('~/.mem0/settings.json')
   settings = {}
   if os.path.isfile(settings_file):
       with open(settings_file) as f:
           settings = json.load(f)
   settings['global_search'] = True
   with open(settings_file, 'w') as f:
       json.dump(settings, f, indent=2)
   print('Global search enabled')
   "
   ```

2. Print:
   ```
   Global search enabled.
   Searches now return all memories across all users and projects.
   Writes still use the current user_id and app_id.
   Restart the session for the change to take effect.
   ```

### If `--no-global` flag is provided:

1. Set `global_search: false` in `~/.mem0/settings.json` using the Bash tool:

   ```bash
   python3 -c "
   import json, os
   settings_file = os.path.expanduser('~/.mem0/settings.json')
   settings = {}
   if os.path.isfile(settings_file):
       with open(settings_file) as f:
           settings = json.load(f)
   settings['global_search'] = False
   with open(settings_file, 'w') as f:
       json.dump(settings, f, indent=2)
   print('Global search disabled')
   "
   ```

2. Print:
   ```
   Global search disabled.
   Searches now return only memories scoped to the current project.
   Restart the session for the change to take effect.
   ```

### If a project name is provided (no flags):

1. If no project name was given, ask: "What project_id should this directory use?"

2. Write the mapping to `~/.mem0/project_map.json` using the Bash tool:

   ```bash
   python3 -c "
   import json, os
   map_file = os.path.expanduser('~/.mem0/project_map.json')
   mapping = {}
   if os.path.isfile(map_file):
       with open(map_file) as f:
           mapping = json.load(f)
   mapping[os.getcwd()] = '<PROJECT_NAME>'
   os.makedirs(os.path.dirname(map_file), exist_ok=True)
   with open(map_file, 'w') as f:
       json.dump(mapping, f, indent=2)
   print(f'Mapped {os.getcwd()} -> <PROJECT_NAME>')
   "
   ```

   (Replace `<PROJECT_NAME>` with the user's chosen project name.)

3. Verify by searching for existing memories:
   - Call `search_memories` with `query="project"`, `filters={"AND": [{"user_id": "<active_user_id>"}, {"app_id": "<PROJECT_NAME>"}]}`, `top_k=1`

4. Print:
   ```
   Switched to project <PROJECT_NAME>.
   <N> memories found for this project.
   Note: This override persists across sessions for this directory.
   ```

## Output formatting

IMPORTANT: Do NOT use markdown in your output. OpenCode TUI renders text verbatim — markdown like **bold**, ## headers, and | table | syntax appears as raw characters. Use plain text with indentation for structure. Use dashes for lists. Use spaces to align columns instead of markdown tables.
