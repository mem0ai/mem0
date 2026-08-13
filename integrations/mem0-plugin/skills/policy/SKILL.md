---
name: policy
description: Views or sets the project's memory-extraction policy (what Mem0 remembers vs ignores) stored in mem0.md. Use when the user says set a memory policy, custom instructions, what should mem0 remember, tell mem0 to ignore X, or asks to see/change the current instructions.
---

# Mem0 Policy

The project's memory policy lives in a `## Instructions` section of `mem0.md` at
the repo root. It is version-controlled and shared by the whole team, and it maps
to Mem0's `custom_instructions` (what to extract / ignore). An optional
`## Agent Instructions` section maps to `agent_custom_instructions` (guidance for
agent-scoped memories only).

The policy takes effect on the **next session** (mem0.md is re-parsed on
SessionStart) and is applied automatically on the plugin's memory writes.

## Execution

### Step 1: Determine intent from the argument

`/mem0:policy` is invoked as `/mem0:policy [<subcommand>] <text>`:

| Argument | Action |
|---|---|
| _(none)_ or `show` | Show the current policy |
| `set <text>` or free text | Set/replace the `## Instructions` (custom) policy |
| `agent <text>` | Set/replace the `## Agent Instructions` policy |
| `clear` | Remove both policy sections |

### Step 2: Locate mem0.md

`mem0.md` sits at the repo root (the current working directory). If it does not
exist yet and the user is setting a policy, you will create it.

### Step 3a: Show

Run `python3 "$CLAUDE_PLUGIN_ROOT/scripts/parse_mem0_config.py" --key instructions .`
and `--key agent_instructions .` (or read `mem0.md` directly). Print:

```
Memory policy for this project (mem0.md):
  Instructions:       <text, or "(none)">
  Agent Instructions: <text, or "(none)">
```

If `mem0.md` is absent, say there is no policy yet and offer to set one.

### Step 3b: Set / clear

Edit `mem0.md`, adding or replacing the target section. Keep the instruction a
short prose paragraph (what to remember, what to ignore). Example:

```markdown
## Instructions
Remember architecture decisions, API contracts, and team conventions.
Ignore transient debugging output, stack traces, and anything resembling a secret.
```

- Preserve any other existing sections (`## Retention`, `## Categories`, etc.).
- If the section already exists, replace its body; otherwise append the section.
- For `clear`, delete the `## Instructions` and `## Agent Instructions` sections.

### Step 4: Confirm

```
Updated memory policy in mem0.md.
Takes effect next session. Commit mem0.md to share it with your team.
```

Remind the user that `## Agent Instructions` only affects agent-scoped memories,
so it is a no-op unless memories are written with an `agent_id`.
