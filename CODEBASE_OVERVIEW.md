# Mem0 Codebase Overview & Architecture

## 🎯 Project Overview

**Mem0** is an intelligent memory layer for AI applications that enables personalized interactions. The project consists of:

1. **Core Mem0 Library** - The main Python SDK for memory management
2. **OpenMemory (Jean Memory)** - A SaaS application built on top of Mem0, providing cloud-hosted memory services

## 🏗️ Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Interfaces                           │
├─────────────────────┬───────────────────┬──────────────────────┤
│   Next.js Web UI    │   MCP Integration │    Direct API        │
│ (jean-memory-ui)    │  (Claude/LLMs)    │   Integration        │
└──────────┬──────────┴─────────┬─────────┴──────────┬───────────┘
           │                    │                     │
           └────────────────────┴─────────────────────┘
                                │
                    ┌───────────▼────────────┐
                    │   FastAPI Backend      │
                    │  (jean-memory-api)     │
                    │                        │
                    │  • Auth (Supabase JWT) │
                    │  • REST API Endpoints  │
                    │  • MCP Server (SSE)    │
                    └───────────┬────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
┌───────▼────────┐    ┌────────▼────────┐    ┌────────▼────────┐
│   Supabase     │    │   PostgreSQL    │    │    Qdrant       │
│ (Auth Service) │    │  (Metadata DB)  │    │ (Vector Store)  │
└────────────────┘    └─────────────────┘    └─────────────────┘
```

## 📁 Repository Structure

```
mem0/
├── 📚 Core Library
│   ├── mem0/              # Main Python SDK
│   ├── mem0-ts/           # TypeScript SDK
│   ├── examples/          # Usage examples
│   └── tests/             # Test suite
│
├── 🚀 OpenMemory (SaaS Application)
│   ├── openmemory/
│   │   ├── api/           # Backend API
│   │   │   ├── app/       # FastAPI application
│   │   │   │   ├── routers/      # API endpoints
│   │   │   │   ├── services/     # Business logic
│   │   │   │   ├── integrations/ # External services
│   │   │   │   ├── models.py     # SQLAlchemy models
│   │   │   │   ├── auth.py       # Authentication
│   │   │   │   └── mcp_server.py # MCP integration
│   │   │   └── alembic/   # Database migrations
│   │   │
│   │   └── ui/            # Frontend application
│   │       ├── app/       # Next.js app router
│   │       ├── components/# React components
│   │       └── lib/       # Utilities & API clients
│   │
│   └── 📋 Documentation
│       ├── README.md
│       ├── STATUS.md      # Project status
│       └── DOCUMENT_STORAGE_PLAN.md
│
└── 🔧 Configuration
    ├── render.yaml        # Render deployment
    ├── docker-compose.yml # Local development
    └── pyproject.toml     # Python dependencies
```

## 🔑 Key Components

### 1. **Authentication System**
- **Provider**: Supabase Auth
- **Method**: JWT tokens
- **Flow**: 
  ```
  User Login → Supabase → JWT Token → API Authorization
  ```

### 2. **Memory Management**
- **Storage**: Hybrid approach
  - PostgreSQL: Metadata, user info, app configs
  - Qdrant: Vector embeddings for semantic search
- **Operations**: Add, Search, List, Delete memories
- **Multi-tenancy**: User-isolated memory spaces

### 3. **MCP (Model Context Protocol) Integration**
- **Purpose**: Enables LLMs (like Claude) to interact with memories
- **Endpoints**: Dynamic per-user SSE endpoints
- **Tools Available**:
  - `add_memories`: Store new memories
  - `search_memory`: Semantic search
  - `list_memories`: View all memories
  - `delete_all_memories`: Clear memory

### 4. **Document Storage (Planned)**
- **Goal**: Store full documents alongside memory snippets
- **Design**: Two-tier system
  - Quick access to summaries
  - On-demand full content retrieval
- **Use Cases**: Essays, code files, articles

## 🔄 Data Flow

```
1. User Action (Web UI / MCP Tool)
        ↓
2. API Request (with JWT auth)
        ↓
3. FastAPI Route Handler
        ↓
4. Business Logic Layer
        ├─→ PostgreSQL (metadata)
        └─→ Qdrant (vectors)
        ↓
5. Response to Client
```

## 🛠️ Technology Stack

### Backend
- **Framework**: FastAPI (Python)
- **Database**: PostgreSQL + SQLAlchemy
- **Vector Store**: Qdrant
- **Auth**: Supabase
- **LLM**: OpenAI GPT-4
- **Memory SDK**: Mem0

### Frontend
- **Framework**: Next.js 14 (App Router)
- **UI**: React + Tailwind CSS
- **State**: React Hooks
- **API Client**: Axios
- **Auth**: Supabase JS Client

### Infrastructure
- **Deployment**: Render.com
- **Container**: Docker
- **CI/CD**: GitHub Actions

## 🚀 Quick Start Guide

### Local Development

1. **Clone & Navigate**
   ```bash
   git clone https://github.com/mem0ai/mem0.git
   cd mem0/openmemory
   ```

2. **Environment Setup**
   ```bash
   # Backend
   cp api/.env.example api/.env
   # Add: OPENAI_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_KEY
   
   # Frontend
   cp ui/.env.example ui/.env.local
   # Add: NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY
   ```

3. **Run Services**
   ```bash
   docker compose up -d
   ```

4. **Access**
   - API: http://localhost:8765
   - UI: http://localhost:3000

### Production URLs
- **Frontend**: https://jean-memory-ui.onrender.com
- **API**: https://jean-memory-api.onrender.com
- **API Docs**: https://jean-memory-api.onrender.com/docs

## 📊 Database Schema

### Core Tables
- **users**: User accounts (Supabase ID linked)
- **apps**: Applications per user
- **memories**: Stored memory entries
- **documents**: Full document storage (planned)
- **categories**: Memory categorization

### Relationships
```
User (1) → (N) Apps
User (1) → (N) Memories
App (1) → (N) Memories
Memory (N) ↔ (N) Categories
Document (1) → (N) Memories
```

## 🔐 Security Features

1. **Authentication**: Supabase JWT validation
2. **Authorization**: User-scoped data access
3. **Data Isolation**: Multi-tenant architecture
4. **API Security**: CORS configuration, rate limiting (planned)

## 📈 Current Status

- ✅ **MVP Complete**: Full multi-tenant functionality
- ✅ **Production Deployed**: Live on Render.com
- ✅ **MCP Integration**: Working with Claude
- 🎯 **Next**: Document storage, enhanced security, monitoring

## 🤝 Contributing

The project welcomes contributions in:
- Bug fixes and feature implementations
- Documentation improvements
- Testing and feedback
- Integration examples

See `CONTRIBUTING.md` for guidelines.

---

This overview provides a high-level understanding of the Mem0 codebase, focusing on the OpenMemory SaaS application. The system is designed for scalability, security, and ease of integration with AI applications. 