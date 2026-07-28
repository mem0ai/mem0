---
name: config
description: Show or change how aggressively mem0 captures and retrieves memories, and switch between dual and full memory mode. Use when the user says mem0 is storing too much or too little, wants fewer or more memories injected, or asks about memory settings.
---

# Configure memory behavior

Two dials and one mode. Show the current state first, then change only what was asked for.

```bash
mem0-agent config                      # show everything
mem0-agent config --capture <level>    # conservative | balanced | aggressive
mem0-agent config --retrieval <level>  # conservative | balanced | aggressive
mem0-agent config --mode <mode>        # dual | full
```

## capture — what gets stored

| Level | Captures |
|---|---|
| `conservative` | explicit "remember this", and corrections only |
| `balanced` *(default)* | + decisions and root-caused gotchas |
| `aggressive` | + completed goals and procedures the assistant proposes |

Mechanical noise — progress updates, ETAs, heartbeats, file lists, repo-file contents — is
dropped at every level. That is not configurable, because storing it is what made the
previous version useless.

## retrieval — what gets injected

| Level | Injects |
|---|---|
| `conservative` | pins, preferences and the open thread (~600 tokens); no error lookups |
| `balanced` *(default)* | the full pack (≤1500 tokens) and high-confidence error lookups |
| `aggressive` | a larger pack (≤2500 tokens) and more eager error lookups |

## mode — how mem0 coexists with repo memory files

- `dual` — `CLAUDE.md` and friends stay authoritative for repo-local notes; mem0 handles
  durable, cross-machine knowledge.
- `full` — mem0 is the only memory layer; writes to `MEMORY.md` are blocked and native
  auto-memory should be turned off.

Mode is stored per project, so a repo with a curated `CLAUDE.md` can stay `dual` while
another goes `full`.

## Guidance

If the user complains about noise in their context, lower `retrieval` before touching
`capture` — the corpus is usually fine and the injection is what they're feeling. If they
say memories are missing, check `mem0-agent stats` first: a memory written minutes ago is
still being extracted, and extraction is asynchronous.
