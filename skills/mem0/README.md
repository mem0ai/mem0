# Mem0 Skill for Claude

Add persistent memory to any AI application in minutes using [Mem0 Platform](https://app.mem0.ai?utm_source=oss&utm_medium=skill-mem0-readme) or the open-source self-hosted SDK.

> **Part of the Mem0 Skill Graph:** See also [mem0-cli](../mem0-cli/SKILL.md) (terminal) and [mem0-vercel-ai-sdk](../mem0-vercel-ai-sdk/SKILL.md) (Vercel AI SDK).

## What This Skill Does

When installed, Claude can:

- **Set up Mem0** in your Python or TypeScript project (Platform or OSS)
- **Integrate memory** into your existing AI app (LangChain, CrewAI, OpenAI Agents, LangGraph, LlamaIndex, etc.)
- **Generate working code** using real API references and tested patterns
- **Search live docs** on demand for the latest Mem0 documentation

## Installation

### CLI (Claude Code, OpenCode, OpenClaw, or any tool that supports skills)

```bash
npx skills add https://github.com/mem0ai/mem0 --skill mem0
```

### Claude.ai

1. Download this `skills/mem0` folder as a ZIP
2. Go to **Settings > Capabilities > Skills**
3. Click **Upload skill** and select the ZIP

### Claude API (Skills API)

```bash
curl -X POST https://api.anthropic.com/v1/skills \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "mem0", "source": "https://github.com/mem0ai/mem0/tree/main/skills/mem0"}'
```

### Prerequisites

- A Mem0 Platform API key ([Get one here](https://app.mem0.ai/dashboard/api-keys?utm_source=oss&utm_medium=skill-mem0-readme))
- Python 3.10+ or Node.js 18+
- Set the environment variable:

  ```bash
  export MEM0_API_KEY="m0-your-api-key"
  ```

## Quick Start

After installing, just ask Claude:

- "Set up mem0 in my project"
- "Add memory to my chatbot"
- "Help me search user memories with filters"
- "Integrate mem0 with my LangChain app"
- "Add graph memory to track entity relationships"

## What's Inside

```text
skills/mem0/
├── SKILL.md                    # Skill definition and instructions
├── README.md                   # This file
├── LICENSE                     # Apache-2.0
├── client/                     # Language-specific SDK references (Platform + OSS)
│   ├── python.md               # Python SDK (MemoryClient + Memory OSS)
│   ├── node.md                 # TypeScript SDK (MemoryClient + Memory OSS)
│   └── differences.md          # Python vs TypeScript comparison
├── scripts/
│   └── mem0_doc_search.py      # Search live Mem0 docs on demand
└── references/                 # Documentation (loaded on demand)
    ├── quickstart.md           # Full quickstart (Python, TS, cURL)
    ├── sdk-guide.md            # All SDK methods (Python + TypeScript)
    ├── api-reference.md        # REST endpoints, filters, memory object
    ├── architecture.md         # Processing pipeline, lifecycle, scoping, performance
    ├── features.md             # Retrieval, graph, categories, MCP, webhooks, multimodal
    ├── integration-patterns.md # LangChain, CrewAI, OpenAI Agents, LangGraph, LlamaIndex, etc.
    └── use-cases.md            # 7 real-world patterns with Python + TypeScript code
```

## Links

- [Mem0 Platform Dashboard](https://app.mem0.ai?utm_source=oss&utm_medium=skill-mem0-readme)
- [Mem0 Documentation](https://docs.mem0.ai)
- [Mem0 GitHub](https://github.com/mem0ai/mem0)
- [API Reference](https://docs.mem0.ai/api-reference)

## License

Apache-2.0
