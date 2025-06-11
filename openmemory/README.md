# Jean Memory - Your Personal Memory Layer for AI

Jean Memory is your personal memory layer for AI applications, available as both a cloud-hosted service and for local development. It allows you to build AI applications with personalized memories while giving you complete control over your data.

## Features

- 🧠 **Personal Memory Storage**: Add and organize your thoughts, preferences, and experiences
- 🔍 **Smart Search**: Find relevant memories using natural language queries
- 💬 **Conversational Interface**: Ask questions about yourself and get personalized responses
- 📄 **Document Integration**: Upload and analyze documents, PDFs, and text files
- 🔗 **Substack Integration**: Sync your Substack posts for comprehensive memory building
- 🎯 **MCP Compatible**: Works with Claude Desktop via Model Context Protocol

## 🚀 Quick Start

### Cloud Service (Recommended)

*   **Live Application:** [https://jeanmemory.com](https://jeanmemory.com)
*   **Frontend UI:** [https://app.jeanmemory.com](https://app.jeanmemory.com)
*   **Backend API:** `https://api.jeanmemory.com`
*   **API Documentation:** [https://api.jeanmemory.com/docs](https://api.jeanmemory.com/docs)

To use the cloud version, simply visit the Frontend UI link above, sign up or log in, and follow the instructions to connect your MCP clients using the provided production API endpoints.

![Jean Memory Dashboard](https://github.com/user-attachments/assets/3c701757-ad82-4afa-bfbe-e049c2b4320b)

## 🎥 **Video Tutorial**

Watch this 5-minute step-by-step tutorial to get Jean Memory working with your AI tools:

<p align="center">
  <a href="https://youtu.be/qXe4mEaCN9k">
    <img src="https://img.youtube.com/vi/qXe4mEaCN9k/maxresdefault.jpg" alt="Jean Memory Setup Tutorial" width="600">
  </a>
</p>

**[▶️ Watch the Full Tutorial on YouTube](https://youtu.be/qXe4mEaCN9k)**

*Perfect for beginners! Covers everything from installing Node.js to testing your first memory.*

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

## 🧠 Local Development Setup

This project is configured for a hybrid development model, where the backend services (API, database) run in Docker, and the frontend UI runs on your local machine. This provides a fast and efficient development experience.

Follow these steps for a first-time setup:

### Prerequisites
- Docker Desktop
- Node.js (v18+)
- Python 3.8+
- OpenAI API key

### One-Command Setup

```bash
# Clone and setup everything automatically
git clone <repository-url>
cd mem0/openmemory
make setup
```

This will:
- Create all necessary environment files
- Start Docker containers (PostgreSQL + Qdrant)
- Install dependencies
- Initialize database
- **Automatically configure for local development** (clears QDRANT_API_KEY for Docker compatibility)

### 🔧 Configuration

1. **Add your OpenAI API key**:
   ```bash
   # Edit the API configuration
   nano api/.env
   
   # Update this line:
   OPENAI_API_KEY=your_actual_openai_api_key_here
   ```

2. **Start the services**:
   ```bash
   # Start backend services (API + Database)
   make backend
   
   # In another terminal, start the UI
   make ui-local
   ```

3. **Access the application**:
   - **API**: http://localhost:8765
   - **UI**: http://localhost:3000

### 🤖 Claude Desktop Integration (MCP)

After setup, connect Claude Desktop to your local Jean Memory:

1. **Install supergateway** (if not already installed):
   ```bash
   npm install -g supergateway
   ```

2. **Configure Claude Desktop**:
   Add to `~/.anthropic/claude_desktop_config.json`:
   ```json
   {
     "mcpServers": {
       "local-memory": {
         "command": "npx",
         "args": ["supergateway", "sse://http://localhost:8765/mcp/claude/sse/local_dev_user"]
       }
     }
   }
   ```

3. **Restart Claude Desktop** and you'll have access to these tools:
   - `ask_memory` - Fast conversational memory search
   - `add_memories` - Store new information about yourself
   - `search_memory` - Quick keyword-based search
   - `list_memories` - Browse your stored memories
   - `deep_memory_query` - Comprehensive analysis of all content

### 🔧 Local vs Production Configuration

The setup scripts automatically handle the key differences:

**Local Development** (Docker):
- `QDRANT_API_KEY=""` (empty - no SSL/auth needed)
- `QDRANT_HOST=localhost`
- `DATABASE_URL=postgresql://...@localhost:5432/...`

**Production** (Cloud):
- `QDRANT_API_KEY=your_cloud_api_key`
- `QDRANT_HOST=your-cluster.cloud.qdrant.io`
- `DATABASE_URL=postgresql://...@production-host/...`

**Important**: The setup process ensures your local environment won't have SSL connection issues with Docker Qdrant.

## 🛠️ Development Commands

```bash
# Start all services
make up                    # Full Docker mode
make backend              # Backend only (recommended)
make ui-local             # UI development mode

# Management
make down                 # Stop all services
make status              # Check service status
make restart-backend     # Restart backend services

# Setup & troubleshooting
make setup               # Initial setup
make help               # Show all commands
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

## Architecture

- **Backend**: FastAPI + PostgreSQL + Qdrant vector database
- **Frontend**: Next.js + React + Tailwind CSS
- **Memory**: mem0 library for intelligent memory management
- **AI**: OpenAI GPT models for processing and responses
- **MCP**: Server-Sent Events (SSE) endpoints for Claude Desktop integration

## Troubleshooting

### Memory Tools Show SSL Errors
If you see `[SSL: WRONG_VERSION_NUMBER]` errors:
1. Check that `QDRANT_API_KEY=""` (empty) in `api/.env`
2. Restart backend: `make restart-backend`
3. Local Docker Qdrant doesn't use SSL authentication

### MCP Connection Issues
1. Ensure services are running: `make status`
2. Check Claude Desktop config syntax
3. Restart Claude Desktop after config changes
4. Verify endpoint: `curl http://localhost:8765/mcp/claude/sse/local_dev_user`

### Port Conflicts
```bash
# Kill processes on common ports
lsof -ti:8765 | xargs kill -9  # API port
lsof -ti:3000 | xargs kill -9  # UI port
lsof -ti:5432 | xargs kill -9  # PostgreSQL port
```

## Production Deployment

For production deployment, see [DEPLOYMENT_GUIDE.md](../DEPLOYMENT_GUIDE.md).

Key differences:
- Use cloud Qdrant with API key
- Set up Supabase authentication
- Configure proper environment variables
- Use production-grade database

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test locally with `make setup && make backend && make ui-local`
5. Submit a pull request

## License

[Add your license here]
