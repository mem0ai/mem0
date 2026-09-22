# Mem0 Vercel AI SDK Skill for Claude

Add persistent memory to any Vercel AI SDK application using [@mem0/vercel-ai-provider](https://www.npmjs.com/package/@mem0/vercel-ai-provider).

## What This Skill Does

When installed, Claude can:

- **Set up `@mem0/vercel-ai-provider`** in your TypeScript or Next.js project
- **Generate working code** using the wrapped model (`createMem0`) or standalone utilities (`retrieveMemories`, `addMemories`, etc.)
- **Configure multi-provider setups** (OpenAI, Anthropic, Google, Groq, Cohere)
- **Integrate memory** into streaming responses, structured output, and API routes

## Installation

### CLI (Claude Code, OpenCode, OpenClaw, or any tool that supports skills)

```bash
npx skills add https://github.com/mem0ai/mem0 --skill mem0-vercel-ai-sdk
```

### Claude.ai

1. Download this `skills/mem0-vercel-ai-sdk` folder as a ZIP
2. Go to **Settings > Capabilities > Skills**
3. Click **Upload skill** and select the ZIP

### Claude API (Skills API)

```bash
curl -X POST https://api.anthropic.com/v1/skills \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "mem0-vercel-ai-sdk", "source": "https://github.com/mem0ai/mem0/tree/main/skills/mem0-vercel-ai-sdk"}'
```

### Prerequisites

- **Node.js 18+**
- **Vercel AI SDK v5** (`ai` package version 5.x)
- A Mem0 Platform API key ([Get one here](https://app.mem0.ai/dashboard/api-keys?utm_source=oss&utm_medium=skill-mem0-vercel-ai-sdk-readme))
- An LLM provider API key (OpenAI, Anthropic, Google, Groq, or Cohere)
- Set environment variables:

  ```bash
  export MEM0_API_KEY="m0-xxx"
  export OPENAI_API_KEY="sk-xxx"  # or your chosen provider's key
  ```

## Quick Start

After installing, just ask Claude:

- "Add memory to my Vercel AI SDK app"
- "Set up mem0 with streamText in my Next.js API route"
- "Use retrieveMemories with Anthropic instead of the wrapped model"
- "Show me how to use graph memories with the Vercel AI provider"
- "Help me store conversation history with addMemories"

## What's Inside

```text
skills/mem0-vercel-ai-sdk/
├── SKILL.md                          # Skill definition and instructions
├── README.md                         # This file
├── LICENSE                           # Apache-2.0
└── references/                       # Documentation (loaded on demand)
    ├── provider-api.md               # createMem0, Mem0Provider, types, config
    ├── memory-utilities.md           # addMemories, retrieveMemories, getMemories, searchMemories
    └── usage-patterns.md             # Working examples: streaming, Next.js, multi-provider, graph
```

## Links

- [Mem0 Platform Dashboard](https://app.mem0.ai?utm_source=oss&utm_medium=skill-mem0-vercel-ai-sdk-readme)
- [Mem0 Documentation](https://docs.mem0.ai)
- [Mem0 GitHub](https://github.com/mem0ai/mem0)
- [@mem0/vercel-ai-provider on npm](https://www.npmjs.com/package/@mem0/vercel-ai-provider)
- [Vercel AI SDK Documentation](https://ai-sdk.dev/docs)

## Skill Graph

This skill is part of the Mem0 skill graph. The three Mem0 skills (mem0, mem0-cli, mem0-vercel-ai-sdk) each cover a different interface to the same Mem0 Platform API.

## License

Apache-2.0
