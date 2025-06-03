# Jean Memory - Your Personal Memory Layer for AI

Jean Memory is your personal memory layer for AI applications, available as both a cloud-hosted service and for local development. It allows you to build AI applications with personalized memories while giving you complete control over your data.

## 🚀 Quick Start

### Cloud Service (Recommended)

*   **Live Application:** [https://jeanmemory.com](https://jeanmemory.com)
*   **Frontend UI:** [https://app.jeanmemory.com](https://app.jeanmemory.com)
*   **Backend API:** `https://api.jeanmemory.com`
*   **API Documentation:** [https://api.jeanmemory.com/docs](https://api.jeanmemory.com/docs)

To use the cloud version, simply visit the Frontend UI link above, sign up or log in, and follow the instructions to connect your MCP clients using the provided production API endpoints.

![Jean Memory Dashboard](https://github.com/user-attachments/assets/3c701757-ad82-4afa-bfbe-e049c2b4320b)

## ⭐ Upgrade to Jean Memory Pro

Take your AI memory to the next level with **Jean Memory Pro** - advanced features for power users and developers who want more control and capabilities.

### 🚀 Pro Features

- **🎯 Priority Support** - Get help fast with dedicated support channels
- **💡 Feature Requests** - Request new features and vote on development priorities  
- **🔍 Advanced Search** - Semantic search, date filters, and smart categorization
- **📈 Higher Limits** - 10x more memories and API calls vs. free tier
- **📦 Data Export** - Download and backup all your memories anytime
- **🚪 Early Access** - Get beta features weeks before general release
- **🏷️ Custom Categories** - Organize memories with personalized tags and folders
- **⚡ Bulk Operations** - Manage hundreds of memories with powerful batch tools

[![Upgrade to Pro](https://img.shields.io/badge/⭐_Upgrade_to_Pro-$19.99-9333ea?style=for-the-badge&logo=stripe&logoColor=white)](https://buy.stripe.com/fZuaEX70gev399t4tMabK00)

**[→ Upgrade to Jean Memory Pro for $19.99](https://buy.stripe.com/fZuaEX70gev399t4tMabK00)**

Join our Pro community and help shape the future of AI memory management! 🚀

## 🔧 Local Development Setup

If you wish to run Jean Memory locally for development or complete privacy, follow these steps:

### Prerequisites (Local Development)

- **Docker and Docker Compose** - For containerized deployment
- **Python 3.9+** - If modifying backend outside Docker
- **Node.js 18+** - If modifying frontend outside Docker
- **OpenAI API Key** - Set in `openmemory/api/.env` for LLM functionality
- **Supabase Project** - For authentication and user management:
    - Set up a free [Supabase project](https://supabase.com)
    - Configure `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` in `openmemory/api/.env`
    - Configure `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` in `openmemory/ui/.env.local`
- **Qdrant Vector Database** - For memory storage:
    - The `docker-compose.yml` includes a local Qdrant service
    - Or use [Qdrant Cloud](https://cloud.qdrant.io/) by configuring `QDRANT_HOST` and `QDRANT_API_KEY`

### Quickstart (Local Development)

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/jonathan-politzki/your-memory.git
    cd your-memory/openmemory
    ```

2.  **Set up Environment Variables:**
    
    **Backend Configuration:**
    ```bash
    cp api/.env.example api/.env
    ```
    Edit `api/.env` with your:
    - `OPENAI_API_KEY` - Your OpenAI API key
    - `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` - From your Supabase project
    - `QDRANT_HOST` and `QDRANT_API_KEY` - If using Qdrant Cloud (optional)
    
    **Frontend Configuration:**
    ```bash
    # Create ui/.env.local if it doesn't exist
    touch ui/.env.local
    ```
    Edit `ui/.env.local` with your:
    - `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` - From your Supabase project
    - `NEXT_PUBLIC_API_URL=http://localhost:8765` - For local development

3.  **Build and Run with Docker Compose:**
    ```bash
    make build  # or docker compose build
    make up     # or docker compose up -d
    ```

4.  **Access Local Services:**
    - **Jean Memory UI:** `http://localhost:3000`
    - **Jean Memory API:** `http://localhost:8765`
    - **API Documentation:** `http://localhost:8765/docs`
    - **Qdrant Dashboard:** `http://localhost:6333/dashboard`

## 📁 Project Structure

```
openmemory/
├── api/          # Backend APIs + MCP server
│   ├── app/      # FastAPI application
│   ├── Dockerfile
│   └── requirements.txt
├── ui/           # Frontend React application
│   ├── app/      # Next.js pages
│   ├── components/
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml
└── Makefile
```

## 🔗 MCP Integration

Jean Memory provides MCP (Model Context Protocol) endpoints for connecting to AI applications:

### Supported Clients
- **Claude Desktop** - Anthropic's AI assistant
- **Cursor** - AI-powered code editor
- **Windsurf** - Codeium's AI editor
- **Cline** - VS Code AI extension
- **Any MCP-compatible application**

### Connection Setup
1. Sign up at [jeanmemory.com](https://jeanmemory.com)
2. Get your personalized MCP command from the dashboard
3. Run the command to connect your AI tool:
   ```bash
   npx install-mcp i https://api.jeanmemory.com/mcp/claude/sse/your-user-id --client claude
   ```
4. Restart your AI application

## 🛠️ Development Commands

```bash
# Build containers
make build

# Start services
make up

# Stop services
make down

# View logs
make logs

# Clean up
make clean

# Restart specific service
docker compose restart api
docker compose restart ui
```

## 🧪 Testing

```bash
# Run backend tests
cd api
python -m pytest

# Run frontend tests
cd ui
npm test

# Test MCP connection
curl http://localhost:8765/mcp/health
```

## 🤝 Contributing

We welcome contributions from developers who believe in the future of personalized AI and privacy-first technology.

### Areas for Contribution:
- **🔒 Privacy Features** - Client-side encryption, zero-knowledge architecture
- **🔌 Integrations** - New MCP clients and AI applications
- **📚 Documentation** - Setup guides, API documentation, tutorials
- **🐛 Bug Fixes** - Improve stability and performance
- **✨ Features** - Advanced search, team collaboration, enterprise features

### How to Contribute:

1. **Fork the repository**
2. **Create a feature branch:** `git checkout -b feature/amazing-feature`
3. **Make your changes** with clear, well-tested code
4. **Commit your changes:** `git commit -m 'Add amazing feature'`
5. **Push to your branch:** `git push origin feature/amazing-feature`
6. **Open a Pull Request** with a clear description

### Development Guidelines:
- Follow existing code style and conventions
- Add tests for new functionality
- Update documentation for any API changes
- Ensure Docker builds work properly

## 🌟 Community

Join us in building the future of AI memory management! We're a team of developers passionate about making AI more personal and private.

**Ways to get involved:**
- ⭐ Star the repository
- ⭐ [Upgrade to Pro](https://buy.stripe.com/fZuaEX70gev399t4tMabK00) ($19.99)
- 🐛 Report bugs via [GitHub Issues](https://github.com/jonathan-politzki/your-memory/issues)
- 💡 Suggest features
- 📖 Contribute to documentation
- 🔧 Submit pull requests

## 📄 Licensing

The `openmemory` module contains original work and modifications by **Jean Technologies**, Copyright (c) 2025 Jean Technologies. These contributions are proprietary and all rights are reserved. Unauthorized copying, modification, or distribution of this proprietary code is strictly prohibited.

For licensing inquiries regarding these portions, please contact [hello@jeanmemory.com](mailto:hello@jeanmemory.com).

A copy of the proprietary notice can be found in the `LICENSE-JEAN.md` file in this directory.

**Attribution:** This project is a fork of and incorporates code from the [`mem0` project](https://github.com/mem0ai/mem0), which is licensed under the Apache 2.0 License. The original Apache 2.0 license and copyright notices for `mem0` are maintained where applicable.

## 🆘 Support & Contact

- **📖 Documentation:** [jeanmemory.com/docs](https://jeanmemory.com/docs)
- **🐛 Issues:** [GitHub Issues](https://github.com/jonathan-politzki/your-memory/issues)
- **✉️ Email:** [hello@jeanmemory.com](mailto:hello@jeanmemory.com)
- **🌐 Website:** [jeanmemory.com](https://jeanmemory.com)

---

<p align="center">
  <strong>Building the future of personalized AI, one memory at a time.</strong><br>
  Built with ❤️ by <a href="https://jeanmemory.com">Jean Technologies</a>
</p>
