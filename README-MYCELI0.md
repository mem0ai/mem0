# myceli0

**Enterprise-grade memory layer for AI agents with production reliability**

> 🍄 myceli0 (my-seal-ee-oh) - Like mycelium, the neural network of fungi that connects and shares information across vast distances, myceli0 creates an intelligent memory network for your AI agents.

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Based on mem0](https://img.shields.io/badge/based%20on-mem0-purple)](https://github.com/mem0ai/mem0)

## Overview

myceli0 is a production-ready fork of [mem0](https://github.com/mem0ai/mem0) enhanced with enterprise features for reliability, scalability, and observability. Built for serious AI applications that require robust memory management.

### Why myceli0?

While mem0 provides excellent core memory functionality, myceli0 extends it with:

- **🔄 Async Background Processing** - Non-blocking memory operations with automatic recovery
- **📊 Graph Visualization** - Neo4j-powered memory relationship mapping
- **⚙️ Dynamic Prompt Management** - Database-backed, versioned prompt system with UI
- **🛡️ Production Reliability** - Startup recovery, stuck memory detection, state management
- **🎯 Temporal Entity Extraction** - Time-aware memory with event tracking
- **👥 Enhanced Multi-tenancy** - Advanced app management, ownership transfer, superuser support
- **📈 Processing States** - Track memory lifecycle from creation to activation

## Quick Start

### Prerequisites
- Docker & Docker Compose
- OpenAI API Key (or compatible LLM endpoint)
- Neo4j (optional, for graph features)

### Installation

```bash
# Clone the repository
git clone https://github.com/chronicler-ai/myceli0.git
cd myceli0

# Set up environment
cp openmemory/.env.template openmemory/.env
# Edit .env and add your OPENAI_API_KEY

# Start services
cd openmemory
make build
make up
```

Access:
- **OpenMemory UI**: http://localhost:3333
- **API Documentation**: http://localhost:8765/docs
- **MCP Server**: `http://localhost:8765/mcp/<client>/<user>/sse`

## Architecture

myceli0 consists of two main components:

### 1. **mem0 Core Library** (`/mem0`)
The foundational Python SDK for memory operations:
- Vector store integrations (Qdrant, Pinecone, Chroma, etc.)
- Graph store integrations (Neo4j, Memgraph, Kuzu)
- LLM integrations (OpenAI, Anthropic, Ollama, etc.)
- Memory extraction, update, and search algorithms

### 2. **OpenMemory Application** (`/openmemory`)
Production-ready service with web UI:
- FastAPI backend with REST + MCP server
- Next.js frontend with React
- Multi-user/multi-app management
- Advanced configuration UI
- Graph visualization dashboard

## Key Features

### Async Background Processing

Memory creation happens in the background with automatic recovery:

```python
# Creates placeholder immediately, processes in background
response = await create_memory_async(
    text="User prefers dark mode",
    user_id="john",
    app_name="my-app"
)
# Returns instantly with memory ID
# Processing happens in background
```

**Features:**
- Non-blocking API responses
- Automatic retry on failure
- Startup recovery for crashed tasks
- Processing state tracking (`pending` → `processing` → `active`)

### Graph Visualization

Explore memory relationships through Neo4j:

```python
# Query graph data
GET /api/v1/graph/data?user_id=john&limit=100

# Returns nodes and relationships for visualization
```

- Interactive graph UI
- Filter by user, app, or entity type
- Temporal relationship tracking
- Entity connection mapping

### Dynamic Prompt Management

Customize memory extraction prompts through UI:

- Version-controlled prompts
- Database-backed storage
- Live prompt editing
- Multiple prompt types (extraction, update, etc.)
- A/B testing support

### Temporal Entity Extraction

Time-aware memory with structured metadata:

```python
# Input: "I'm getting married next week at 4pm at the botanical gardens"
# Extracts:
{
  "isEvent": true,
  "isRelationship": true,
  "entities": ["botanical gardens", "wedding"],
  "timeRanges": [{
    "start": "2025-12-15T16:00:00Z",
    "end": "2025-12-15T18:00:00Z",
    "name": "wedding ceremony"
  }],
  "emoji": "💒"
}
```

## Production Reliability

### Startup Recovery

Automatically recovers memories stuck in processing state on server restart:

```python
# On startup, myceli0:
# 1. Finds all memories in 'processing' state
# 2. Retries mem0 processing
# 3. Updates state to 'active' or 'deleted'
# 4. Creates audit trail in history
```

### State Management

Track memory lifecycle:
- `pending` - Queued for processing
- `processing` - Currently being processed
- `active` - Successfully created
- `deleted` - Soft deleted
- `archived` - Archived for retention

### Manual Recovery Endpoint

```bash
# Check for and recover stuck memories
POST /api/v1/memories/actions/recover-stuck
```

## API Documentation

Full API documentation available at: http://localhost:8765/docs

### Key Endpoints

**Memories:**
- `POST /api/v1/memories` - Create memory (async)
- `GET /api/v1/memories` - List memories
- `PUT /api/v1/memories/{id}` - Update memory
- `DELETE /api/v1/memories` - Bulk delete

**Graph:**
- `GET /api/v1/graph/data` - Get graph visualization data

**Prompts:**
- `GET /api/v1/prompts` - List prompts
- `POST /api/v1/prompts` - Create prompt
- `PUT /api/v1/prompts/{id}` - Update prompt

**Apps:**
- `GET /api/v1/apps` - List apps
- `POST /api/v1/apps` - Create app
- `DELETE /api/v1/apps/{id}` - Delete app with memory migration

## MCP Integration

Use with Claude Desktop, Cline, or any MCP-compatible client:

```bash
# Configure MCP client
npx @openmemory/install local \
  http://localhost:8765/mcp/claude/your-user-id/sse \
  --client claude
```

**MCP Tools:**
- `add_memories` - Add new memories
- `search_memory` - Search existing memories
- `list_memories` - List all memories

## Configuration

### Environment Variables

**API (.env):**
```bash
OPENAI_API_KEY=sk-...
NEO4J_URL=neo4j://neo4j:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password
DATABASE_URL=sqlite:///data/openmemory.db
```

**UI (.env):**
```bash
NEXT_PUBLIC_API_URL=http://localhost:8765
NEXT_PUBLIC_USER_ID=your-user-id
```

### Vector Store Support

myceli0 supports all mem0 vector stores:
- Qdrant (default)
- Pinecone
- Chroma
- Weaviate
- PostgreSQL (pgvector)
- And many more...

### LLM Support

Works with any mem0-compatible LLM:
- OpenAI (GPT-4, GPT-3.5)
- Anthropic (Claude)
- Ollama (local models)
- Azure OpenAI
- Custom OpenAI-compatible endpoints

## Development

### Project Structure

```
myceli0/
├── mem0/                    # Core library
│   ├── memory/             # Memory operations
│   ├── vector_stores/      # Vector DB integrations
│   ├── graphs/             # Graph DB integrations
│   └── llms/               # LLM integrations
├── openmemory/             # Application
│   ├── api/                # FastAPI backend
│   │   ├── app/
│   │   │   ├── routers/    # API endpoints
│   │   │   ├── models.py   # Database models
│   │   │   └── utils/      # Utilities
│   │   └── main.py         # App entry
│   └── ui/                 # Next.js frontend
│       ├── app/            # Pages & components
│       ├── hooks/          # React hooks
│       └── store/          # Redux store
└── docs/                   # Documentation
```

### Running Tests

```bash
# Backend tests
cd openmemory/api
pytest

# Frontend tests
cd openmemory/ui
pnpm test
```

### Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Comparison: myceli0 vs mem0

| Feature | mem0 (upstream) | myceli0 |
|---------|----------------|----------|
| Core memory operations | ✅ | ✅ |
| Vector stores | ✅ | ✅ |
| Graph stores | ✅ | ✅ |
| Async API | ✅ | ✅ |
| **Background processing** | ❌ | ✅ |
| **Processing states** | ❌ | ✅ |
| **Startup recovery** | ❌ | ✅ |
| **Graph visualization UI** | ❌ | ✅ |
| **Prompt management UI** | ❌ | ✅ |
| **Temporal extraction** | ❌ | ✅ |
| **Enhanced multi-tenancy** | ❌ | ✅ |
| **App ownership transfer** | ❌ | ✅ |

## Roadmap

- [ ] Metrics & monitoring dashboard
- [ ] Webhook support for memory events
- [ ] Advanced search with filters
- [ ] Memory clustering & categorization
- [ ] Export/import capabilities
- [ ] Multi-modal memory (images, audio)
- [ ] Federation across multiple instances

## License

Apache License 2.0

**Original Work:**
- Copyright 2023 Taranjeet Singh and the Mem0 team
- Licensed under Apache License 2.0

**Modifications:**
- Copyright 2025 Stu Alexander (Chronicler AI)
- Licensed under Apache License 2.0

This project is based on [mem0](https://github.com/mem0ai/mem0). All modifications maintain the same Apache 2.0 license. See [LICENSE](LICENSE) and [NOTICE](NOTICE) files for details.

## Acknowledgments

- **mem0 team** - For creating the excellent foundation
- **Chronicler AI** - For supporting enterprise development
- **Community contributors** - Thank you!

## Support

- **Issues**: https://github.com/chronicler-ai/myceli0/issues
- **Discussions**: https://github.com/chronicler-ai/myceli0/discussions
- **Original mem0 Discord**: https://mem0.dev/DiG

## Links

- [mem0 (upstream)](https://github.com/mem0ai/mem0)
- [mem0 Documentation](https://docs.mem0.ai)
- [Chronicler AI](https://github.com/chronicler-ai)

---

Built with 🍄 by [Chronicler AI](https://github.com/chronicler-ai)
