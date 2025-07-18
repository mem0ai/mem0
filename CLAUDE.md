# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Mem0 is an intelligent memory layer for AI assistants and agents, enabling personalized AI interactions. It provides long-term memory capabilities with multi-level memory management (User, Session, Agent state).

## Common Development Commands

### Build and Package
```bash
hatch build                 # Build the package
hatch env create           # Create development environment
pip install -e .          # Install in development mode
```

### Code Quality and Testing
```bash
hatch run format           # Format code with ruff
hatch run lint             # Lint code with ruff
hatch run test             # Run tests
pytest tests/             # Run specific test suite
```

### Using Makefile
```bash
make format               # Format code
make lint                 # Lint code
make test                 # Run tests
make install              # Create hatch environment
make install_all          # Install all optional dependencies
```

### Multi-Python Testing
```bash
make test-py-3.9          # Test on Python 3.9
make test-py-3.10         # Test on Python 3.10
make test-py-3.11         # Test on Python 3.11
```

## Architecture Overview

### Core Components

1. **Memory Management (`mem0/memory/`)**
   - `main.py`: Core Memory and AsyncMemory classes
   - `graph_memory.py`: Graph-based memory implementation
   - `storage.py`: SQLite-based storage backend
   - `base.py`: Base memory interface

2. **LLM Integration (`mem0/llms/`)**
   - Supports multiple providers: OpenAI, Anthropic, Groq, Azure OpenAI, etc.
   - Structured output support for OpenAI and Azure OpenAI
   - Base class pattern for easy extensibility

3. **Vector Stores (`mem0/vector_stores/`)**
   - Multiple vector database support: Chroma, Pinecone, Qdrant, Weaviate, etc.
   - Unified interface through base class
   - Configuration-driven setup

4. **Embeddings (`mem0/embeddings/`)**
   - Support for various embedding models
   - Providers: OpenAI, Azure OpenAI, Hugging Face, Vertex AI, etc.

5. **Graph Database (`mem0/graphs/`)**
   - Neptune integration for graph-based memory
   - Graph utilities and tools

6. **Client Interface (`mem0/client/`)**
   - REST API client for hosted platform
   - Project management utilities

### Key Design Patterns

- **Factory Pattern**: Used for creating LLM, embedding, and vector store instances
- **Configuration-Driven**: Extensive use of Pydantic models for configuration
- **Async Support**: Both sync and async interfaces throughout
- **Modular Architecture**: Clear separation of concerns between components

## Development Guidelines

### Code Style
- Uses `ruff` for formatting and linting
- Line length limit: 120 characters
- Excludes `embedchain/` and `openmemory/` directories from linting

### Testing
- Tests are located in `tests/` directory
- Organized by component (llms, embeddings, vector_stores, etc.)
- Uses pytest with async support

### Configuration
- Optional dependencies grouped by feature:
  - `graph`: Graph database support
  - `vector_stores`: Vector database integrations
  - `llms`: Additional LLM providers
  - `extras`: Additional utilities

## Important Notes

- The project uses `hatch` as the build backend and environment manager
- Multiple Python versions supported (3.9-3.11)
- Telemetry is implemented for usage tracking
- Memory operations support filtering by user_id, agent_id, and run_id
- The codebase includes both open-source and platform components