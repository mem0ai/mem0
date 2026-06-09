---
name: switch-project
description: Overrides the auto-detected project scope to read and write memories under a different project ID. Use when working across multiple projects, accessing memories from another context, or when auto-detection resolves to the wrong project.
---

# Switch Project

Override the automatic project_id detection for the current session.

## Usage

- `/mem0-switch <project-name>` — switch to a specific project scope

## Execution

### Step 1: Parse input

If no project name was given, ask: "What project should this session use? Provide a project name or ID."

### Step 2: Switch context

The `/mem0-switch` command updates the in-memory scope context for the current session. All subsequent memory operations will target the new project.

### Step 3: Verify

Use `mem0_memory` tool with `action="search"`, `query="project"`, `scope="project"` to verify there are accessible memories under the new project scope.

### Step 4: Confirm

```
Switched to project <project-name>.
<N> memories found for this project.
Note: This override lasts for the current session only.
```

If zero memories found under the new project:
```
Switched to project <project-name>.
No existing memories found — this appears to be a new project scope.
```
