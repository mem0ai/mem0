# 🏠 Jean Memory Local Development Infrastructure

## 📋 Table of Contents
- [Architecture Overview](#-architecture-overview)
- [Local Development Diagram](#-local-development-diagram)
- [Development Modes](#-development-modes)
- [Infrastructure Components](#️-infrastructure-components)
- [Data Storage & Persistence](#️-data-storage--persistence)
- [Environment Configuration](#-environment-configuration)
- [Development Workflow](#-development-workflow)
- [Make Commands Reference](#-make-commands-reference)
- [Port Mapping & Networking](#-port-mapping--networking)
- [MCP Integration Setup](#-mcp-integration-setup)
- [Performance Optimizations](#-performance-optimizations)
- [Troubleshooting Guide](#-troubleshooting-guide)
- [Development vs Production Differences](#-development-vs-production-differences)

---

## 🌐 Architecture Overview

Jean Memory's local development environment uses a **hybrid architecture** optimized for developer productivity:

- **Backend Services**: Docker containers (API, PostgreSQL, Qdrant)
- **Frontend Development**: Native Node.js process for maximum performance  
- **Authentication**: Bypassed with fixed USER_ID for simplified development
- **Data Persistence**: Docker volumes for consistent state

## 🎯 Local Development Diagram

```mermaid
graph TB
    subgraph "Developer Machine"
        subgraph "Local Host"
            DEV[Developer IDE]
            CLI[Terminal Make Commands]
            BROWSER[Browser :3000]
        end
        
        subgraph "Docker Desktop"
            subgraph "memory_network"
                API[FastAPI Container :8765]
                POSTGRES[PostgreSQL 15 :5432]
                QDRANT[Qdrant Vector DB :6333]
            end
        end
        
        subgraph "Native Process"
            UI[Next.js Dev Server :3000]
        end
    end
    
    subgraph "External Services"
        OPENAI[OpenAI API]
        GEMINI[Gemini API]
    end
    
    DEV --> UI
    CLI --> API
    BROWSER --> UI
    UI --> API
    API --> POSTGRES
    API --> QDRANT
    API --> OPENAI
    API --> GEMINI
```

## 🔄 Development Modes

### 1. Hybrid Mode (Recommended)
```bash
make backend    # Backend in Docker
make ui-local   # Frontend runs locally
```

**Benefits:**
- ⚡ Ultra-fast frontend hot reload
- 🏠 Consistent backend environment
- 💾 Lower resource usage

### 2. Full Docker Mode
```bash
make up  # All services in Docker
```

**Benefits:**
- 🔒 Complete environment isolation
- 📦 Consistent across developers

## 🔧 Infrastructure Components

### Backend API (Docker)
- **Container**: `jeanmemory_api_service`
- **Image**: Python 3.12-slim with FastAPI
- **Port**: 8765
- **Features**: Live reload, auto-migration, auth bypass

### PostgreSQL Database (Docker)
- **Container**: `jeanmemory_postgres_service`
- **Image**: postgres:15
- **Port**: 5432
- **Data**: Persistent Docker volume

### Qdrant Vector DB (Docker)
- **Container**: `jeanmemory_qdrant_service`
- **Ports**: 6333 (HTTP), 6334 (gRPC)
- **Config**: No SSL/auth for local development

### Next.js Frontend (Local)
- **Process**: Native Node.js
- **Port**: 3000
- **Features**: Turbopack, HMR, TypeScript

## 🛢️ Data Storage & Persistence

### Docker Volumes
```yaml
Persistent Volumes:
  postgres_data:    # PostgreSQL database files
  qdrant_data:      # Vector embeddings and indices
  ui_node_modules:  # Node.js dependencies (Docker UI mode)
  ui_next_cache:    # Next.js build cache (Docker UI mode)
```

### Source Code Mounts
```yaml
Volume Mounts:
  ./openmemory/api -> /usr/src/app     # API live reloading
  ./openmemory/ui -> /app              # UI development (Docker mode)
```

### Data Directories
```bash
Local Development Data:
├── postgres_data/          # PostgreSQL data files
├── qdrant_data/           # Vector database storage
├── openmemory/api/.env    # Backend environment configuration
├── openmemory/ui/.env.local  # Frontend environment configuration
└── logs/                  # Application logs (if configured)
```

## 🔧 Environment Configuration

### Backend (.env)
```bash
USER_ID=00000000-0000-0000-0000-000000000001
DATABASE_URL=postgresql://jean_memory:memory_password@postgres_db:5432/jean_memory_db
QDRANT_HOST=qdrant_db
QDRANT_API_KEY=                    # Empty for local
OPENAI_API_KEY=your_key_here
```

### Frontend (.env.local)
```bash
NEXT_PUBLIC_API_URL=http://localhost:8765
NEXT_PUBLIC_USER_ID=local_dev_user
NEXT_TELEMETRY_DISABLED=1
```

### Docker Compose Environment
```yaml
API Service Environment:
  USER_ID: 00000000-0000-0000-0000-000000000001
  DATABASE_URL: postgresql://jean_memory:memory_password@postgres_db:5432/jean_memory_db
  QDRANT_HOST: qdrant_db
  QDRANT_PORT: 6333
  PYTHONUNBUFFERED: 1

UI Service Environment (Docker mode):
  NEXT_PUBLIC_API_URL: http://localhost:8765
  NEXT_PUBLIC_USER_ID: local_dev_user
  NODE_OPTIONS: --max-old-space-size=2048
  NEXT_TELEMETRY_DISABLED: 1
```

## 🚀 Development Workflow

### Initial Setup
```bash
make setup      # Create env files
# Edit openmemory/api/.env with your API keys
make build      # Install dependencies, build images
```

### Daily Development
```bash
make backend    # Start backend services
make ui-local   # Start frontend (in new terminal)
```

### Useful Commands
```bash
make status           # Check service status
make restart-backend  # Restart backend only
make clean           # Reset everything
make logs            # View Docker logs
```

## 🌐 Port Mapping

| Service | Local Port | Purpose |
|---------|------------|---------|
| Frontend | 3000 | Next.js dev server |
| Backend API | 8765 | FastAPI application |
| PostgreSQL | 5432 | Database connection |
| Qdrant | 6333/6334 | Vector database |

## 🔗 MCP Integration

### Claude Desktop Setup
```json
// ~/.anthropic/claude_desktop_config.json
{
  "mcpServers": {
    "local-memory": {
      "command": "npx",
      "args": ["supergateway", "sse://http://localhost:8765/mcp/claude/sse/local_dev_user"]
    }
  }
}
```

### Available Tools
- `ask_memory` - Conversational search
- `add_memories` - Store information
- `search_memory` - Keyword search
- `list_memories` - Browse memories

## ⚡ Performance Features

### Frontend Optimizations
- **Turbopack**: Ultra-fast bundling
- **HMR**: Instant hot module replacement  
- **Memory**: 4GB Node.js heap allocation
- **Native Speed**: No Docker overhead

### Backend Optimizations
- **Auto-reload**: Uvicorn development mode
- **Volume Mounts**: Direct file system access
- **Debug Mode**: Enhanced error reporting

## 🔍 Troubleshooting

### Backend Issues
```bash
# Check Docker status
docker ps

# Restart services
make restart-backend

# View logs
make logs
```

### Frontend Issues
```bash
# Clear cache
rm -rf openmemory/ui/.next

# Reinstall dependencies
cd openmemory/ui && pnpm install
```

### Database Issues
```bash
# Check health
docker exec -it jeanmemory_postgres_service pg_isready

# Reset data
make clean && make backend
```

## 🔄 Local vs Production

| Aspect | Local | Production |
|--------|-------|------------|
| **Auth** | Bypassed | Supabase JWT |
| **Database** | Docker container | Render.com managed |
| **Vector DB** | Docker (no auth) | Qdrant Cloud |
| **Frontend** | Dev server | Production build |
| **SSL** | Disabled | Required |

## 📦 Docker Volumes

- `postgres_data` - Database files
- `qdrant_data` - Vector storage
- `ui_node_modules` - Dependencies (Docker mode)
- `ui_next_cache` - Build cache (Docker mode)

## 🛠️ Prerequisites

- **Docker Desktop** - Container runtime
- **Node.js 18+** - Frontend development
- **pnpm** - Fast package manager (recommended)
- **OpenAI API Key** - Required for AI features

---

*This hybrid approach provides the optimal balance of consistency, performance, and developer experience for Jean Memory development.*

## 📚 Additional Resources

### Development Tools
- **Docker Desktop**: [docker.com/products/docker-desktop](https://docker.com/products/docker-desktop)
- **Node.js**: [nodejs.org](https://nodejs.org) (v18+ recommended)
- **pnpm**: [pnpm.io](https://pnpm.io) (faster package manager)
- **PostgreSQL Client**: [postgresql.org/docs](https://postgresql.org/docs)

### Documentation
- **FastAPI Docs**: [fastapi.tiangolo.com](https://fastapi.tiangolo.com)
- **Next.js Docs**: [nextjs.org/docs](https://nextjs.org/docs)
- **Docker Compose**: [docs.docker.com/compose](https://docs.docker.com/compose)
- **Qdrant Docs**: [qdrant.tech/documentation](https://qdrant.tech/documentation)

### Monitoring & Debugging
- **Qdrant Dashboard**: `http://localhost:6333/dashboard`
- **FastAPI Interactive Docs**: `http://localhost:8765/docs`
- **PostgreSQL Admin**: Consider pgAdmin for database management

---

*Last Updated: June 11, 2025*
*Documentation Version: 1.0* 