# mem0-oss-to-platform — Pipeline Skill

Migrate a project from the Mem0 Open Source (self-hosted) SDK to the Mem0 Platform (hosted) SDK, end to end. The skill audits where Mem0 is used, writes a reviewable migration plan, and executes it after you approve.

> **This is a pipeline skill, not a reference skill.** Invoke it when you want your agent to migrate an existing project's Mem0 integration from OSS to the Platform. For day-to-day SDK coding help, install [`mem0`](../mem0/SKILL.md) instead.
>
> **Part of the Mem0 Skill Graph:**
> - Reference: [mem0](../mem0/SKILL.md) · [mem0-cli](../mem0-cli/SKILL.md) · [mem0-vercel-ai-sdk](../mem0-vercel-ai-sdk/SKILL.md)
> - Pipeline: [mem0-integrate](../mem0-integrate/SKILL.md) → [mem0-test-integration](../mem0-test-integration/SKILL.md) · **mem0-oss-to-platform** (this skill)

## What This Skill Does

When invoked, your assistant will:

- **Discover** every place Mem0 is used in the project — imports, client init, config blocks, call sites, dependencies, env, and local infra
- **Verify** the exact API against the installed SDK rather than guessing
- **Map** each OSS `Memory` usage to its hosted `MemoryClient` equivalent (Python and TypeScript)
- **Flag** everything that isn't a clean 1:1 and needs a human decision
- **Write** a reviewable `MEM0_MIGRATION_PLAN.md`, then **execute it after you approve** — strictly scoped to the Mem0 integration, with no unrelated refactors

## When to Use

Trigger phrases:

- "Migrate my Mem0 setup to the Platform"
- "Switch from self-hosted Mem0 to MemoryClient"
- "Use my Mem0 API key instead of a local Qdrant"
- "Move Mem0 to the hosted/managed service"

Do **not** use this skill for general SDK usage (install [`mem0`](../mem0/SKILL.md)), or to add Mem0 to a repo that doesn't use it yet (use [`mem0-integrate`](../mem0-integrate/SKILL.md)).

## Installation

### CLI (Claude Code, Codex, OpenCode, OpenClaw, or any tool that supports skills)

```bash
npx skills add https://github.com/mem0ai/mem0 --skill mem0-oss-to-platform
```

### Claude.ai

1. Download this `skills/mem0-oss-to-platform` folder as a ZIP
2. Go to **Settings > Capabilities > Skills**
3. Click **Upload skill** and select the ZIP

### Claude API (Skills API)

```bash
curl -X POST https://api.anthropic.com/v1/skills \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "mem0-oss-to-platform", "source": "https://github.com/mem0ai/mem0/tree/main/skills/mem0-oss-to-platform"}'
```

### Prerequisites

- A Mem0 Platform API key ([get one](https://app.mem0.ai/dashboard/api-keys))
- An existing project that uses the Mem0 OSS SDK

## Workflow

```
(invoke skill)  →  audits the repo's Mem0 usage,
                   writes MEM0_MIGRATION_PLAN.md,
                   stops for your review
(approve)       →  executes the plan and verifies
                   (compile/import, real-API smoke test)
```

## Links

- [Mem0 Platform Dashboard](https://app.mem0.ai)
- [Mem0 Documentation](https://docs.mem0.ai)
- [OSS → Platform migration guide](https://docs.mem0.ai/migration/oss-v2-to-v3)
- [Platform vs OSS comparison](https://docs.mem0.ai/platform/platform-vs-oss)

## License

Apache-2.0
