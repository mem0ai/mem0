# Mem0 Skills for AI Coding Assistants

Mem0 ships structured skill definitions for Claude Code, Cursor, OpenCode, OpenClaw, and any assistant that supports the [skills standard](https://github.com/anthropic-experimental/skills). Skills teach the assistant how to work with Mem0 — either by loading SDK knowledge into context, or by executing an end-to-end workflow on demand.

## Two Categories

### Reference skills — always on

Installed once, loaded into context so the assistant writes correct Mem0 code. Use these for day-to-day development.

| Skill | Surface | Install |
|-------|---------|---------|
| [`mem0`](./mem0/) | Python + TypeScript SDKs (Platform + OSS), framework integrations | `npx skills add https://github.com/mem0ai/mem0 --skill mem0` |
| [`mem0-cli`](./mem0-cli/) | Terminal workflows (`mem0` CLI, both Node and Python) | `npx skills add https://github.com/mem0ai/mem0 --skill mem0-cli` |
| [`mem0-vercel-ai-sdk`](./mem0-vercel-ai-sdk/) | `@mem0/vercel-ai-provider` and `createMem0` | `npx skills add https://github.com/mem0ai/mem0 --skill mem0-vercel-ai-sdk` |

### Pipeline skills — run on demand

Invoked as a slash command to execute a specific end-to-end workflow. These do real work: they create branches, write tests, run code.

| Skill | Trigger | Install |
|-------|---------|---------|
| [`mem0-integrate`](./mem0-integrate/) | `/mem0-integrate` — wire Mem0 into an existing repo via TDD | `npx skills add https://github.com/mem0ai/mem0 --skill mem0-integrate` |
| [`mem0-test-integration`](./mem0-test-integration/) | `/mem0-test-integration` — verify what `/mem0-integrate` produced | `npx skills add https://github.com/mem0ai/mem0 --skill mem0-test-integration` |

The two pipeline skills are designed to run in sequence on the same workspace:

```
/mem0-integrate          →  mem0-integrate/<slug> branch + .mem0-integration/ artifacts
/mem0-test-integration   →  scorecard (compile + runtime verification, real API smoke test)
```

## Choosing a Skill

- **Writing Mem0 code in a new or existing project?** → `mem0`
- **Using the terminal CLI?** → `mem0-cli`
- **Building with `@ai-sdk/*`?** → `mem0-vercel-ai-sdk`
- **Want the assistant to wire Mem0 into an existing repo for you?** → `mem0-integrate`, then `mem0-test-integration`

## Links

- [Vibecoding with Mem0](https://docs.mem0.ai/vibecoding) — canonical landing page
- [Claude Code integration](https://docs.mem0.ai/integrations/claude-code)
- [Mem0 Platform Dashboard](https://app.mem0.ai)
- [Mem0 Documentation](https://docs.mem0.ai)

## License

Apache-2.0
