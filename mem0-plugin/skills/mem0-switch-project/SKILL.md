---
name: mem0-switch-project
description: Override the auto-detected project scope
---

# Mem0 Switch Project

Override the automatic project_id detection for the current directory.

## Usage

The user provides a project name as an argument: `/mem0:switch-project <project-name>`

## Execution

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
   - Call `search_memories` with `query="project"`, `filters={"AND": [{"user_id": "<id>"}, {"app_id": "<PROJECT_NAME>"}]}`, `limit=1`

4. Print:
   ```
   Switched to project <PROJECT_NAME>.
   <N> memories found for this project.
   Note: This override persists across sessions for this directory.
   ```
