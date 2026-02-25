# Mem0 Repository Summary

## Overview

**Mem0** ("mem-zero") is an intelligent memory layer for AI applications that enables persistent, personalized interactions. It combines LLMs with vector-based storage to remember user preferences, adapt to individual needs, and continuously learn over time. Mem0 is a Y Combinator S24 company.

**Key Performance Claims:**
- 26% higher accuracy vs OpenAI Memory on the LOCOMO benchmark
- 91% faster responses than full-context approaches
- 90% lower token usage than full-context approaches

---

## Repository Structure

```
mem0/
├── mem0/              # Core Python SDK
├── mem0-ts/           # TypeScript/Node.js SDK
├── vercel-ai-sdk/     # Vercel AI SDK integration
├── server/            # REST API server (FastAPI)
├── openmemory/        # Self-hosted memory UI + MCP server
├── embedchain/        # RAG framework (embedded library)
├── evaluation/        # Benchmarks and evaluation tools
├── examples/          # Demo applications
├── cookbooks/         # Jupyter notebook tutorials
├── docs/              # Documentation (Mintlify)
├── tests/             # Test suite
└── .github/           # CI/CD workflows
```

---

## Core Architecture

### Memory Processing Pipeline

1. **Input Processing** — Accepts messages/text, supports multi-modal inputs, scoped by user/agent/session
2. **Fact Extraction** — LLM extracts relevant facts from conversations using a system prompt
3. **Memory Update** — Compares new facts with existing memories; applies ADD, UPDATE, DELETE, or NONE operations
4. **Storage** — Persists to vector store for semantic search, SQLite for history, optional graph DB for relationships
5. **Retrieval** — Semantic search via embeddings, graph queries for relationships, metadata filtering

### Memory Levels

| Level | Scope | Use Case |
|-------|-------|----------|
| User | `user_id` | Personal preferences, history |
| Agent | `agent_id` | Agent-specific knowledge |
| Session | `run_id` | Conversation-scoped context |

### Supported Operations

- **Add** — Store new memories from conversations
- **Search** — Semantic retrieval with filters
- **Get All** — Retrieve all memories for a scope
- **Update** — Modify existing memories
- **Delete** — Remove specific memories
- **Reset** — Clear all memories for a scope
- **History** — Track memory changes over time

---

## Provider Ecosystem

### LLM Providers (22+)

OpenAI (default), Azure OpenAI, Anthropic (Claude), Google Gemini, Groq, DeepSeek, AWS Bedrock, LiteLLM, Together, Ollama, LMStudio, XAI, Sarvam, and more.

### Embedding Providers (16+)

OpenAI (default), Azure OpenAI, Google Gemini, VertexAI, HuggingFace, Ollama, LMStudio, Together, AWS Bedrock, Langchain, and more.

### Vector Store Backends (17+)

Qdrant (default), Chroma, FAISS, Milvus, Pinecone, Redis, Weaviate, Supabase, PostgreSQL (pgvector), Elasticsearch, OpenSearch, Azure AI Search, Upstash Vector, Cloudflare, and more.

### Graph Databases

Neo4j, Memgraph — for relationship-based memory storage and retrieval.

All providers are instantiated via a **factory pattern**, making it straightforward to swap backends.

---

## SDKs & Deployment Options

### Python SDK (`mem0ai`)

The primary SDK. Install via `pip install mem0ai`. Supports both synchronous and asynchronous APIs (`Memory` and `AsyncMemory` classes). Configuration is Pydantic-based.

### TypeScript/Node.js SDK (`mem0ai` on npm)

Full TypeScript support with async/await for all operations. Includes both cloud client and open-source implementations.

### Vercel AI SDK Integration

Community-maintained library providing persistent memory with Vercel AI SDK, streaming support, and multi-provider compatibility.

### REST API Server

FastAPI-based server with full CRUD operations, search, and OpenAPI docs. Deployable via Docker Compose.

### OpenMemory (Self-Hosted UI)

A private, portable memory layer with:
- **Backend:** FastAPI MCP server
- **Frontend:** Next.js React UI
- **Deployment:** Docker Compose with a one-command setup script

### Managed Platform

Cloud-hosted at `app.mem0.ai` with API key authentication and a managed infrastructure.

---

## Integrations

- **LangChain** — Chain and agent framework
- **LangGraph** — State machine graphs
- **CrewAI** — Multi-agent coordination
- **AutoGen** — Microsoft autonomous agents
- **Vercel AI SDK** — AI application framework
- **OpenAI Function Calling** — Tool use integration
- **Browser Extension** — Chrome extension for ChatGPT, Perplexity, Claude

---

## Development

| Tool | Purpose |
|------|---------|
| Poetry | Dependency management |
| Ruff | Linting |
| isort | Import sorting |
| pytest | Testing (with pytest-mock, pytest-asyncio) |
| Hatchling | Build system |

**Python:** >=3.9, <4.0
**Current Version:** 0.1.106
**License:** Apache 2.0

---

## Key Technical Patterns

- **Factory pattern** for provider instantiation (LLMs, embeddings, vector stores)
- **Pydantic models** for configuration validation
- **SQLAlchemy** for database abstraction and history tracking
- **Async/await** support throughout the codebase
- **Graph-based memory** for entity relationships alongside vector-based semantic search
