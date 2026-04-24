# mem0-integrate — Pipeline Skill

Wire [Mem0](https://mem0.ai) into an existing repository end-to-end, using a goal-driven, test-first pipeline.

> **This is a pipeline skill, not a reference skill.** Invoke it as `/mem0-integrate` when you want your assistant to do the work of integrating Mem0 into a target repo. For day-to-day SDK coding help, install [`mem0`](../mem0/SKILL.md) instead.
>
> **Part of the Mem0 Skill Graph:**
> - Reference: [mem0](../mem0/SKILL.md) · [mem0-cli](../mem0-cli/SKILL.md) · [mem0-vercel-ai-sdk](../mem0-vercel-ai-sdk/SKILL.md)
> - Pipeline: **mem0-integrate** (this skill) → [mem0-test-integration](../mem0-test-integration/SKILL.md)

## What This Skill Does

When invoked, your assistant will:

- **Detect** the target repo's language and stack automatically
- **Ask** whether to integrate with Mem0 Platform (managed) or Mem0 Open Source (self-hosted)
- **Write failing tests first** — no implementation until tests exist
- **Keep the integration additive and feature-flagged** — existing behavior stays byte-for-byte identical when the flag is unset
- **Produce a local feature branch** (`mem0-integrate/...`) and a `.mem0-integration/` directory of artifacts (`goal.md`, `plan.md`, `product.json`) consumed by the companion verification skill

## When to Use

Trigger phrases:

- "Integrate Mem0 into this repo"
- "Add Mem0 to my project"
- "Wire Mem0 into `<repo>`"
- "How do I add memory to an existing project?"

Do **not** use this skill for general SDK usage (install [`mem0`](../mem0/SKILL.md)), terminal workflows (install [`mem0-cli`](../mem0-cli/SKILL.md)), or Vercel AI SDK integration (install [`mem0-vercel-ai-sdk`](../mem0-vercel-ai-sdk/SKILL.md)).

## Installation

### CLI (Claude Code, OpenCode, OpenClaw, or any tool that supports skills)

```bash
npx skills add https://github.com/mem0ai/mem0 --skill mem0-integrate
```

For verification on the same branch, also install the companion skill:

```bash
npx skills add https://github.com/mem0ai/mem0 --skill mem0-test-integration
```

### Claude.ai

1. Download this `skills/mem0-integrate` folder as a ZIP
2. Go to **Settings > Capabilities > Skills**
3. Click **Upload skill** and select the ZIP

### Claude API (Skills API)

```bash
curl -X POST https://api.anthropic.com/v1/skills \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "mem0-integrate", "source": "https://github.com/mem0ai/mem0/tree/main/skills/mem0-integrate"}'
```

### Prerequisites

- A Mem0 Platform API key ([get one](https://app.mem0.ai/dashboard/api-keys)) *or* a working OSS setup (LLM + vector store)
- Python 3.10+ or Node.js 18+ in the target repo
- A clean working tree on the target repo's default branch

## Workflow

```
/mem0-integrate          →  creates mem0-integrate/<slug> branch,
                            writes .mem0-integration/ artifacts,
                            implements against failing tests
/mem0-test-integration   →  runs the repo's native test suite,
                            executes a real end-to-end smoke flow,
                            produces a scorecard
```

The two skills are loosely coupled — they share the same workspace and branch via `.mem0-integration/`, but the verifier never modifies source.

## Links

- [Mem0 Platform Dashboard](https://app.mem0.ai)
- [Mem0 Documentation](https://docs.mem0.ai)
- [Mem0 GitHub](https://github.com/mem0ai/mem0)
- [Platform vs OSS comparison](https://docs.mem0.ai/platform/platform-vs-oss)

## License

Apache-2.0
