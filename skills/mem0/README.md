# Mem0 Skill for Claude

Add persistent memory to any AI application in minutes using [Mem0 Platform](https://app.mem0.ai).

## What This Skill Does

When installed, Claude can:

- **Set up Mem0** in your Python or TypeScript project
- **Integrate memory** into your existing AI app (LangChain, CrewAI, Vercel AI SDK, OpenAI Agents SDK, Pipecat)
- **Generate working code** using real API references and tested patterns
- **Search Mem0 docs** on demand for the latest information
- **Run CLI scripts** for quick memory operations (add, search, update, delete)

## Installation

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

- A Mem0 Platform API key ([Get one here](https://app.mem0.ai/dashboard/api-keys))
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
├── scripts/                    # Executable CLI tools
│   ├── add_memory.py           # Add memories from CLI
│   ├── search_memory.py        # Search with filters
│   ├── update_memory.py        # Update by ID
│   ├── delete_memory.py        # Delete by ID or bulk
│   ├── get_memories.py         # List memories
│   └── mem0_doc_search.py      # Search latest Mem0 docs
└── references/                 # Documentation (loaded on demand)
    ├── quickstart.md           # Full quickstart (Python, TS, cURL)
    ├── general.md              # API concepts and memory object shape
    ├── add-memory.md           # Add memory (all options, graph, multimodal)
    ├── search-memory.md        # Search (filters, operators, gotchas)
    ├── update-delete.md        # Update and delete operations
    ├── filters.md              # V2 filter system (AND/OR/NOT)
    ├── graph-memory.md         # Graph memory (entity relations)
    ├── features.md             # Categories, webhooks, multimodal, async
    ├── typescript-sdk.md       # TypeScript/JavaScript SDK reference
    ├── integration-patterns.md # LangChain, CrewAI, Vercel AI, OpenAI Agents, Pipecat
    └── use-cases.md            # 7 real-world examples from official cookbooks
```

## Links

- [Mem0 Platform Dashboard](https://app.mem0.ai)
- [Mem0 Documentation](https://docs.mem0.ai)
- [Mem0 GitHub](https://github.com/mem0ai/mem0)
- [API Reference](https://docs.mem0.ai/api-reference)

## License

Apache-2.0
