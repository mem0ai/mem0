# u-mem0 Quick Start Guide

> **The Memory Layer for Personalized AI with Shadow Intelligence**

## What is u-mem0?

u-mem0 (pronounced "you-mem-zero") is a fork of mem0 featuring:
- ✨ Async background processing with automatic recovery
- 📊 Interactive Neo4j graph visualization
- ⏰ Temporal entity extraction and event detection
- 🎯 Dynamic prompt management with version control
- 🏗️ Production-ready reliability features

Based on [mem0](https://github.com/mem0ai/mem0) with enhancements by [Ushadow](https://github.com/ushadow-io).

---

## For Users: Get Started in 5 Minutes

### 1. Pull and Run with Docker

```bash
# Download production compose file
curl -O https://raw.githubusercontent.com/ushadow-io/u-mem0/main/docker-compose-prod.yml

# Create .env file
cat > .env << EOF
API_KEY=$(openssl rand -hex 32)
USER=your-username
NEXT_PUBLIC_API_URL=http://localhost:8765
EOF

# Start the stack
docker-compose -f docker-compose-prod.yml up -d
```

### 2. Access Services

- **UI**: http://localhost:3333
- **API**: http://localhost:8765/docs
- **Neo4j**: http://localhost:7474 (username: `neo4j`, password: `changeme`)
- **Qdrant**: http://localhost:6333/dashboard

### 3. Secure Your Installation

⚠️ **IMPORTANT**: Change the default Neo4j password in `docker-compose-prod.yml`:

```yaml
NEO4J_AUTH=neo4j/YOUR_SECURE_PASSWORD
NEO4J_PASSWORD=YOUR_SECURE_PASSWORD
```

---

## For Developers: Building from Source

### Prerequisites

- Docker with Buildx support
- GitHub account with token (for publishing)
- Multi-arch builder configured

### Local Development

```bash
# Clone repository
git clone https://github.com/ushadow-io/u-mem0.git
cd u-mem0

# Copy environment template
cp .env.example .env
# Edit .env with your configuration

# Build and run locally
docker-compose up -d
```

### Publishing Images

```bash
# Login to GitHub Container Registry
echo $GITHUB_TOKEN | docker login ghcr.io -u YOUR_USERNAME --password-stdin

# Build and push (one command!)
chmod +x build-and-push.sh
./build-and-push.sh v1.0.0
```

See [DISTRIBUTION.md](DISTRIBUTION.md) for detailed publishing instructions.

---

## Architecture

```
┌─────────────────┐
│   u-mem0 UI     │  Next.js Frontend (port 3333)
│  (Web Interface)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   u-mem0 API    │  FastAPI Backend (port 8765)
│  (Memory Layer) │
└────┬───────┬────┘
     │       │
     ▼       ▼
┌─────────┐ ┌──────────┐
│  Qdrant │ │  Neo4j   │
│ (Vectors)│ │ (Graph)  │
└─────────┘ └──────────┘
```

**Components:**
- **u-mem0 API**: Python/FastAPI backend for memory operations
- **u-mem0 UI**: Next.js frontend for visualization and management
- **Qdrant**: Vector database for semantic search
- **Neo4j**: Graph database for relationship mapping

---

## Key Features from Original mem0

✓ Multi-level memory (user, session, agent)
✓ Adaptive personalization
✓ Cross-platform support (Python, TypeScript)
✓ 30+ LLM integrations
✓ Distributed architecture

## Enhanced Features in u-mem0

🚀 **Async Processing**: Non-blocking memory creation with automatic retry
📈 **Graph Visualization**: Interactive Neo4j relationship explorer
⏱️ **Temporal Analysis**: Time-aware event detection and extraction
🎨 **Dynamic Prompts**: Database-backed prompt versioning and management
🔧 **Production Ready**: Enhanced error handling, state machines, recovery
🛡️ **Multi-tenancy**: Advanced app management with ownership transfer

---

## Common Commands

```bash
# View logs
docker-compose -f docker-compose-prod.yml logs -f

# Stop services
docker-compose -f docker-compose-prod.yml down

# Update to latest version
docker-compose -f docker-compose-prod.yml pull
docker-compose -f docker-compose-prod.yml up -d

# Backup data
docker run --rm -v mem0_data:/data -v $(pwd):/backup ubuntu tar czf /backup/mem0-backup.tar.gz /data

# Restore data
docker run --rm -v mem0_data:/data -v $(pwd):/backup ubuntu tar xzf /backup/mem0-backup.tar.gz -C /
```

---

## Documentation

- **[DISTRIBUTION.md](DISTRIBUTION.md)** - Building and publishing containers
- **[SECURITY.md](SECURITY.md)** - Security best practices and secrets management
- **[NOTICE](NOTICE)** - Attribution and licensing information
- **[LICENSE](LICENSE)** - Apache License 2.0 terms

---

## Support & Community

- 🐛 **Issues**: https://github.com/ushadow-io/u-mem0/issues
- 💬 **Discussions**: https://github.com/ushadow-io/u-mem0/discussions
- 📖 **Docs**: https://github.com/ushadow-io/u-mem0/wiki

---

## Attribution

u-mem0 is based on [mem0](https://github.com/mem0ai/mem0):
- Original Work: Copyright 2023 Taranjeet Singh and the Mem0 team
- Modifications: Copyright 2025 Stu Alexander (Ushadow)
- License: Apache License 2.0

See [NOTICE](NOTICE) file for complete attribution.

---

## License

Licensed under Apache License 2.0. See [LICENSE](LICENSE) for details.

**TL;DR**: You can use, modify, and distribute this software freely, but:
- Include the LICENSE and NOTICE files
- State significant changes you make
- Don't use our trademarks without permission

---

**Built with ❤️ by Ushadow**
