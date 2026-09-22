# mem0-test-integration — Pipeline Skill

Verify a Mem0 integration produced by [`/mem0-integrate`](../mem0-integrate/SKILL.md). Runs in the same workspace on the same branch — installs dependencies, runs the repo's native test suite, then exercises a real end-to-end smoke flow against the user's API key.

> **This is a pipeline skill, not a reference skill.** Invoke it as `/mem0-test-integration` after `/mem0-integrate` has produced a branch to verify. It catches compile and runtime bugs by design — logical integration errors (wrong data stored, wrong scoping) are for human review.
>
> **Part of the Mem0 Skill Graph:**
> - Reference: [mem0](../mem0/SKILL.md) · [mem0-cli](../mem0-cli/SKILL.md) · [mem0-vercel-ai-sdk](../mem0-vercel-ai-sdk/SKILL.md)
> - Pipeline: [mem0-integrate](../mem0-integrate/SKILL.md) → **mem0-test-integration** (this skill)

## What This Skill Does

When invoked, your assistant will:

- **Refuse to start** unless the branch has `.mem0-integration/` artifacts, the working tree is clean, and the right API key is in the environment
- **Install** the repo's dependencies using its native tooling (pip, pnpm, npm, hatch, etc.)
- **Run the native test suite** in two passes: flag-unset (must behave like `main`) and flag-set (new tests run)
- **Execute a real end-to-end smoke flow** against Mem0 Platform (`MEM0_API_KEY`) or OSS (`OPENAI_API_KEY`)
- **Produce a scorecard** — `overall: pass | fail`, per-check reasons, and the reproduction command for each failure

## When to Use

Trigger phrases:

- "Verify the integration"
- "Test the Mem0 integration"
- "Run `/mem0-test-integration`"

Do **not** use this skill to run general project tests (defer to the repo's native test command) or before `/mem0-integrate` has produced a branch on the current workspace.

## Installation

### CLI (Claude Code, Codex, OpenCode, OpenClaw, or any tool that supports skills)

```bash
npx skills add https://github.com/mem0ai/mem0 --skill mem0-test-integration
```

Typically installed alongside the companion pipeline skill:

```bash
npx skills add https://github.com/mem0ai/mem0 --skill mem0-integrate
```

### Claude.ai

1. Download this `skills/mem0-test-integration` folder as a ZIP
2. Go to **Settings > Capabilities > Skills**
3. Click **Upload skill** and select the ZIP

### Claude API (Skills API)

```bash
curl -X POST https://api.anthropic.com/v1/skills \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "mem0-test-integration", "source": "https://github.com/mem0ai/mem0/tree/main/skills/mem0-test-integration"}'
```

### Preconditions

The skill refuses to start unless all of the following are true:

- `.mem0-integration/` directory exists in the repo root
- Current branch starts with `mem0-integrate/`
- Working tree is clean
- The same API key used during `/mem0-integrate` is exported in the environment

## What This Skill Does *Not* Catch

By design, this skill only catches compile and runtime bugs. Logical errors — memories stored with the wrong scoping, retrieval returning the wrong user's data, filter mismatches — are the human reviewer's responsibility.

## Links

- [Mem0 Documentation](https://docs.mem0.ai)
- [Mem0 GitHub](https://github.com/mem0ai/mem0)
- [API Reference](https://docs.mem0.ai/api-reference)

## License

Apache-2.0
