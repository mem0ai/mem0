---
name: remember
description: Store something the user explicitly asked to be remembered, verbatim and immediately. Use when the user says remember this, save this, note that, don't forget, or otherwise asks for a fact to be recorded.
---

# Remember

The user asked for something to be kept. Store it exactly as they said it — this path
bypasses the extraction gate on purpose, because an explicit request is already a decision
that the fact matters.

## How

Run:

```bash
mem0-agent remember --type <type> --text "<the fact, in one self-contained sentence>"
```

Pick `--type` from the six, by what the fact *is*:

| Type | Use when the fact is |
|---|---|
| `preference` | how they want work done (stored at user scope — it follows them across repos) |
| `decision` | a resolved choice, ideally with the reasoning |
| `convention` | a project rule not written in the repo |
| `insight` | a gotcha, constraint, or non-obvious behavior |
| `runbook` | a procedure verified to work |

## Rules

- **One fact per memory.** Two facts means two calls.
- **Self-contained.** "Use pnpm here" is useless later; "This repo uses pnpm, never npm"
  survives on its own.
- **Say it back.** Confirm what was stored in one short line, with the type.
- Don't paraphrase away their meaning. Tighten wording, keep intent.
- If the user's phrasing is a one-off instruction for the current task rather than a
  standing rule, say so and don't store it.
