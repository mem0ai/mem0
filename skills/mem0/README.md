# Mem0 Skill for Claude

Add persistent memory to any AI application in minutes using [Mem0 Platform](https://app.mem0.ai).

## What This Skill Does

When installed, Claude can:

- **Set up Mem0** in your Python or TypeScript project
- **Integrate memory** into your existing AI app (LangChain, CrewAI, Vercel AI, OpenAI Agents, etc.)
- **Generate working code** using real API references and tested patterns
- **Search Mem0 docs** on demand for the latest information

## Installation

### Claude.ai

1. Download this folder as a ZIP
2. Go to Settings > Capabilities > Skills
3. Click "Upload skill" and select the ZIP

### Claude Code

```bash
# Clone and copy to your project
git clone https://github.com/mem0ai/mem0-skills
cp -r mem0-skills/mem0 .claude/skills/
```

### Prerequisites

- A Mem0 Platform API key ([Get one here](https://app.mem0.ai/dashboard/api-keys))
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

## What's Inside

```text
mem0/
├── SKILL.md                    # Skill definition and instructions
├── scripts/                    # Executable CLI tools
│   ├── add_memory.py
│   ├── search_memory.py
│   ├── update_memory.py
│   ├── delete_memory.py
│   ├── get_memories.py
│   └── mem0_doc_search.py
└── references/                 # Documentation (loaded on demand)
    ├── quickstart.md
    ├── general.md
    ├── add-memory.md
    ├── search-memory.md
    ├── update-delete.md
    ├── filters.md
    ├── graph-memory.md
    ├── features.md
    ├── typescript-sdk.md
    └── integration-patterns.md
```

## Links

- [Mem0 Platform Dashboard](https://app.mem0.ai)
- [Mem0 Documentation](https://docs.mem0.ai)
- [Mem0 GitHub](https://github.com/mem0ai/mem0)
- [API Reference](https://docs.mem0.ai/api-reference)

## License

Apache-2.0
