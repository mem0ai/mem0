# 🏗️ Jean Memory Production Infrastructure Documentation

## 📋 Table of Contents
- [Architecture Overview](#-architecture-overview)
- [Infrastructure Diagram](#-infrastructure-diagram)
- [Core Infrastructure](#️-core-infrastructure)
- [Data Storage Architecture](#️-data-storage-architecture)
- [Authentication & Security](#-authentication--security)
- [AI & ML Services](#-ai--ml-services)
- [DNS & CDN](#-dns--cdn)
- [Cost Breakdown](#-cost-breakdown)
- [Data Flow](#-data-flow)
- [Performance Characteristics](#-performance-characteristics)
- [Service URLs](#-service-urls)
- [Environment Variables](#-environment-variables)
- [Monitoring & Health Checks](#-monitoring--health-checks)

---

## 🌐 Architecture Overview

Jean Memory operates on a **multi-cloud, distributed architecture** designed for scalability, performance, and global availability. The system separates concerns across different cloud providers to optimize for their strengths:

- **Render.com**: Core application hosting (backend, frontend, database)
- **Cloudflare Workers**: Edge computing for MCP server
- **Qdrant Cloud**: Vector database for semantic search
- **Supabase**: User authentication and management
- **OpenAI**: AI/ML processing and embeddings

---

## 🎯 Infrastructure Diagram

```mermaid
graph TB
    subgraph "User Access"
        U[User Browser] 
        C[Claude Desktop]
        CR[Cursor IDE]
        W[Windsurf IDE]
    end
    
    subgraph "DNS & CDN Layer"
        CF[Cloudflare DNS]
        CFDNS[jeanmemory.com]
        APICDN[api.jeanmemory.com]
    end
    
    subgraph "Render.com Infrastructure"
        subgraph "Oregon Region"
            UI[jean-memory-ui<br/>Next.js Frontend<br/>Starter Plan - $7/mo]
            API[jean-memory-api<br/>FastAPI Backend<br/>Standard Plan]
            DB[(jonathans-memory-db<br/>PostgreSQL<br/>Basic 256MB - $7/mo)]
        end
    end
    
    subgraph "Cloudflare Workers Edge"
        MCP[MCP Worker<br/>Durable Objects<br/>api.jeanmemory.com]
    end
    
    subgraph "External Cloud Services"
        QD[(Qdrant Cloud<br/>Vector Database)]
        SB[Supabase<br/>Auth Service]
        OAI[OpenAI API<br/>GPT-4o-mini]
        AP[Apify<br/>Twitter Scraping]
        GM[Gemini API<br/>Optional AI]
    end
    
    %% User connections
    U -->|HTTPS| CFDNS
    C -->|MCP Protocol| APICDN
    CR -->|MCP Protocol| APICDN
    W -->|MCP Protocol| APICDN
    
    %% DNS routing
    CFDNS -->|Routes to| UI
    APICDN -->|Routes to| MCP
    
    %% Internal connections
    UI -->|API Calls| API
    MCP -->|Proxies to| API
    API -->|Queries| DB
    
    %% External integrations
    API -->|Embeddings & LLM| OAI
    API -->|Vector Storage| QD
    API -->|User Auth| SB
    API -->|Twitter Data| AP
    API -->|Optional AI| GM
    
    %% Styling
    classDef render fill:#4A90E2,stroke:#333,stroke-width:2px,color:#fff
    classDef cloudflare fill:#F38020,stroke:#333,stroke-width:2px,color:#fff
    classDef external fill:#7ED321,stroke:#333,stroke-width:2px,color:#fff
    classDef user fill:#BD10E0,stroke:#333,stroke-width:2px,color:#fff
    
    class UI,API,DB render
    class MCP,CF,CFDNS,APICDN cloudflare
    class QD,SB,OAI,AP,GM external
    class U,C,CR,W user
```

---

## 🔧 Core Infrastructure

### 1. Primary Hosting: Render.com (Oregon Region)
**Total Monthly Cost: ~$14-21/month**

#### Backend API Service
- **Service Name**: `jean-memory-api` 
- **Service ID**: `srv-d0ogd7ruibrs73c23dg0`
- **URL**: `https://jean-memory-api.onrender.com`
- **Runtime**: Python 3.x (FastAPI + Uvicorn)
- **Plan**: Standard (~$7-14/month)
- **Repository**: `openmemory/api/`
- **Build Command**: `pip install -r requirements.txt`
- **Pre-Deploy**: `alembic upgrade head` (database migrations)
- **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Health Check**: `/health` endpoint
- **Features**: 
  - Auto-scaling based on traffic
  - Background task processing
  - Memory monitoring middleware
  - CORS configuration for multiple origins

#### Frontend UI Service
- **Service Name**: `jean-memory-ui`
- **Service ID**: `srv-d0ogd7ruibrs73c23dfg`
- **URL**: `https://jean-memory-ui.onrender.com` → `https://jeanmemory.com`
- **Runtime**: Node.js (Next.js 15.2.4)
- **Plan**: Starter ($7/month)
- **Repository**: `openmemory/ui/`
- **Build Command**: `pnpm install && pnpm build`
- **Start Command**: `pnpm start`
- **Features**: 
  - Server-Side Rendering (SSR)
  - Static Site Generation (SSG)
  - Optimized image handling
  - PostHog analytics integration

#### Primary Database
- **Service Name**: `jonathans-memory-db`
- **Database ID**: `dpg-d0ofchgdl3ps73epcnj0-a`
- **Type**: PostgreSQL 16
- **Plan**: Basic 256MB ($7/month)
- **Storage**: 1GB
- **Region**: Oregon
- **Database Name**: `openmemory`
- **User**: `openmemory`
- **Features**: 
  - Automated daily backups
  - Connection pooling
  - SSL encryption
  - IP allowlist for security

---

### 2. Edge Computing: Cloudflare Workers
**Cost: ~$5/month (estimated)**

#### MCP Server
- **Worker Name**: `mcp-worker`
- **URL**: `https://api.jeanmemory.com`
- **Technology**: Cloudflare Workers + Durable Objects
- **Purpose**: Model Context Protocol (MCP) server for AI development tools
- **Backend Proxy**: `https://jean-memory-api.onrender.com`
- **Features**:
  - Global edge deployment (300+ locations)
  - WebSocket connections for real-time MCP communication
  - Session management with Durable Objects
  - Request proxying to main API
  - SQLite storage for session state

---

## 🛢️ Data Storage Architecture

### Structured Data (PostgreSQL)
**Location**: Render.com PostgreSQL
**Purpose**: Application metadata, user data, configurations

**Key Tables**:
- `users`: User profiles and authentication data
- `apps`: Connected application configurations
- `memories`: Memory metadata and relationships
- `background_tasks`: Async job queue
- `alembic_version`: Database migration tracking

### Vector Data (Qdrant Cloud)
**Purpose**: Semantic search and memory embeddings
**Configuration**:
- **Collection**: `jonathans_memory_main`
- **Vector Model**: OpenAI `text-embedding-3-small`
- **Dimensions**: 1536
- **Distance Metric**: Cosine similarity

### Session Data (Cloudflare Durable Objects)
**Purpose**: MCP session state and WebSocket connections
**Storage**: SQLite within Durable Objects
**Lifecycle**: Ephemeral, tied to active sessions

---

## 🔐 Authentication & Security

### Primary Authentication Provider
**Service**: Supabase
**Methods Supported**:
- Email/Password authentication
- Google OAuth 2.0
- GitHub OAuth 2.0

**JWT Configuration**:
- Token validation in FastAPI backend
- Global token management in frontend
- Local development bypass mechanism

### Security Features
- **CORS Policy**: Configured for specific origins
- **Environment Variable Encryption**: Render.com environment groups
- **IP Allowlisting**: Database access restrictions
- **SSL/TLS**: End-to-end encryption
- **Authentication Middleware**: JWT verification on all protected routes

---

## 🤖 AI & ML Services

### Primary LLM Provider: OpenAI
**Models Used**:
- **Language Model**: `gpt-4o-mini`
- **Embeddings**: `text-embedding-3-small`
- **Provider**: `openai`

### Optional AI Services
- **Google Gemini**: Alternative language model
- **Apify**: Twitter/X data scraping and integration
- **Custom Integrations**: Substack, document processing

### AI Processing Pipeline
1. **Input Processing**: Text preprocessing and tokenization
2. **Embedding Generation**: Convert text to vectors using OpenAI
3. **Vector Storage**: Store embeddings in Qdrant
4. **Semantic Search**: Query similar memories using vector similarity
5. **Response Generation**: Generate contextual responses using LLM

---

## 🌍 DNS & CDN

### Domain Configuration
- **Primary Domain**: `jeanmemory.com` → Frontend UI
- **API Domain**: `api.jeanmemory.com` → MCP Worker
- **CDN Provider**: Cloudflare (assumed based on setup)

### SSL/TLS
- **Certificates**: Managed by Cloudflare and Render.com
- **Encryption**: TLS 1.3 where supported
- **HSTS**: Enabled for security

---

## 💰 Cost Breakdown (Monthly Estimates)

| Component | Service | Plan/Tier | Estimated Cost |
|-----------|---------|-----------|----------------|
| Backend API | Render.com | Standard | $7-14 |
| Frontend UI | Render.com | Starter | $7 |
| PostgreSQL | Render.com | Basic 256MB | $7 |
| MCP Worker | Cloudflare | Workers Paid | ~$5 |
| Vector Database | Qdrant Cloud | Usage-based | $5-20 |
| Authentication | Supabase | Free tier | $0 |
| OpenAI API | OpenAI | Usage-based | $10-50 |
| Domain/DNS | Cloudflare | Pro (optional) | $0-20 |
| **Total** | | | **$41-123/month** |

### Cost Optimization Notes
- Render.com auto-scaling helps optimize costs based on usage
- Qdrant costs scale with vector storage and queries
- OpenAI costs depend on API usage (embeddings + completions)
- Free tiers available for Supabase (auth) and Cloudflare (basic)

---

## 🔄 Data Flow

### User Authentication Flow
1. **Frontend** → **Supabase** (login/signup)
2. **Supabase** → **Frontend** (JWT token)
3. **Frontend** → **Backend API** (authenticated requests)
4. **Backend API** → **Supabase** (token validation)

### Memory Creation Flow
1. **User Input** → **Frontend** → **Backend API**
2. **Backend API** → **OpenAI** (generate embeddings)
3. **Backend API** → **PostgreSQL** (store metadata)
4. **Backend API** → **Qdrant** (store vector embeddings)
5. **Backend API** → **Frontend** (confirmation response)

### MCP Integration Flow
1. **AI Tool** → **Cloudflare Worker** (MCP protocol)
2. **Cloudflare Worker** → **Backend API** (HTTP proxy)
3. **Backend API** → **External Services** (process request)
4. **Backend API** → **Cloudflare Worker** → **AI Tool** (response)

### Search Query Flow
1. **Search Input** → **Backend API**
2. **Backend API** → **OpenAI** (query embedding)
3. **Backend API** → **Qdrant** (vector similarity search)
4. **Backend API** → **PostgreSQL** (fetch metadata)
5. **Backend API** → **Frontend** (search results)

---

## ⚡ Performance Characteristics

### Global Performance
- **Edge Computing**: MCP server deployed to 300+ Cloudflare locations
- **Regional Concentration**: Core services in Oregon (optimized for US West Coast)
- **CDN**: Static assets cached globally via Cloudflare

### Scalability Features
- **Auto-scaling**: Render services scale automatically based on demand
- **Connection Pooling**: PostgreSQL connections optimized
- **Background Processing**: Async task queue for heavy operations
- **Caching**: Multiple layers of caching for performance

### Monitoring & Observability
- **Health Checks**: Automated health monitoring on all services
- **Logging**: Structured logging with configurable levels
- **Memory Monitoring**: Custom middleware for memory usage tracking
- **Error Tracking**: Comprehensive error handling and reporting

---

## 🔗 Service URLs

### Production URLs
- **Frontend**: `https://jeanmemory.com`
- **Backend API**: `https://jean-memory-api.onrender.com`
- **MCP Server**: `https://api.jeanmemory.com`
- **API Documentation**: `https://jean-memory-api.onrender.com/docs`

### Development URLs
- **Local Frontend**: `http://localhost:3000`
- **Local Backend**: `http://localhost:8765`
- **Local Database**: `postgresql://jean_memory:memory_password@localhost:5432/jean_memory_db`

---

## 🔧 Environment Variables

### Backend API Environment
```bash
# Database
DATABASE_URL=postgresql://...

# Authentication
SUPABASE_URL=https://...
SUPABASE_SERVICE_KEY=...
SUPABASE_ANON_KEY=...

# AI Services
OPENAI_API_KEY=...
LLM_PROVIDER=openai
OPENAI_MODEL=gpt-4o-mini
EMBEDDER_PROVIDER=openai
EMBEDDER_MODEL=text-embedding-3-small

# Vector Database
QDRANT_HOST=...
QDRANT_PORT=6333
QDRANT_API_KEY=...
MAIN_QDRANT_COLLECTION_NAME=jonathans_memory_main

# Optional Services
APIFY_TOKEN=...
GEMINI_API_KEY=...

# Runtime
PYTHONUNBUFFERED=1
LOG_LEVEL=INFO
UVICORN_TIMEOUT_KEEP_ALIVE=75
```

### Frontend Environment
```bash
# API Configuration
NEXT_PUBLIC_API_URL=https://jean-memory-api.onrender.com
NODE_ENV=production

# Authentication (Public Keys)
NEXT_PUBLIC_SUPABASE_URL=...
NEXT_PUBLIC_SUPABASE_ANON_KEY=...

# Local Development
NEXT_PUBLIC_USER_ID=... # Local dev only
```

### MCP Worker Environment
```bash
# Backend Proxy
BACKEND_URL=https://jean-memory-api.onrender.com
```

---

## 📊 Monitoring & Health Checks

### Health Check Endpoints
- **Backend API**: `GET /health`
- **Frontend**: Built-in Next.js health monitoring
- **Database**: Connection health via Render dashboard

### Monitoring Tools
- **Render Dashboard**: Service metrics, logs, and alerts
- **Cloudflare Analytics**: Edge performance and security metrics
- **PostHog**: User analytics and feature usage
- **Custom Logging**: Application-specific metrics and events

### Alerting
- **Service Downtime**: Automatic alerts via Render
- **Error Rates**: Custom error tracking and notifications
- **Performance**: Response time and resource usage monitoring

---

## 📝 Deployment Process

### Automated Deployment
1. **Code Push** → GitHub repository
2. **Webhook** → Render.com (auto-deploy enabled for some services)
3. **Build Process** → Install dependencies and build
4. **Pre-Deploy** → Run database migrations (backend only)
5. **Deploy** → Start new service instances
6. **Health Check** → Verify service health
7. **Traffic Switch** → Route traffic to new instances

### Manual Deployment Options
- **Render CLI**: Manual deploy triggers
- **Dashboard**: One-click deployments
- **API**: Programmatic deployment control

---

## 🔍 Troubleshooting Guide

### Common Issues
1. **CORS Errors**: Check origin configuration in backend
2. **Authentication Failures**: Verify Supabase keys and JWT validation
3. **Database Connection**: Check environment variables and IP allowlist
4. **MCP Connection Issues**: Verify Cloudflare Worker status and backend proxy

### Debug Tools
- **Render Logs**: Real-time service logs
- **Browser DevTools**: Frontend debugging
- **Database Console**: Direct SQL access via Render
- **API Documentation**: `/docs` endpoint for API testing

---

## 📚 Additional Resources

- **Render.com Documentation**: [render.com/docs](https://render.com/docs)
- **Cloudflare Workers**: [developers.cloudflare.com](https://developers.cloudflare.com)
- **Next.js Documentation**: [nextjs.org/docs](https://nextjs.org/docs)
- **FastAPI Documentation**: [fastapi.tiangolo.com](https://fastapi.tiangolo.com)
- **MCP Protocol**: [modelcontextprotocol.io](https://modelcontextprotocol.io)

---

*Last Updated: June 11, 2025*
*Documentation Version: 1.0* 