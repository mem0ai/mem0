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

### Step 1: Initial Setup

First, run the setup command. This will check for prerequisites (like Docker and Node.js) and create the necessary `.env` files for you.

```bash
make setup
```

### Step 2: Add Your API Keys

After the setup command completes, you need to add your API keys to the backend environment file.

1.  Open `openmemory/api/.env` in your editor.
2.  Find the following lines and replace the placeholder text with your actual keys:
    ```
    OPENAI_API_KEY="your-openai-api-key-here"
    GEMINI_API_KEY="your-gemini-api-key-here"
    ```
    You can get your keys from:
    - [OpenAI API Keys](https://platform.openai.com/api-keys)
    - [Google AI Studio](https://makersuite.google.com/app/apikey)

### Step 3: Build the Environment

Now, build the Docker images and install frontend dependencies. This command validates your API keys, installs `pnpm` packages for the UI, and builds the Docker containers.

```bash
make build
```

### Step 4: Run the Application

Once the build is complete, you can start the application. You'll need two separate terminal windows for this.

**In your first terminal**, start the backend services:

```bash
make backend
```
This will start the API, PostgreSQL database, and Qdrant vector database in Docker containers.

**In your second terminal**, start the local UI development server:

```bash
make ui-local
```

### Step 5: Open in Your Browser

That's it! Once both processes are running, you can access the application in your browser:

- **Frontend UI:** [http://localhost:3000](http://localhost:3000)
- **Backend API:** [http://localhost:8765/docs](http://localhost:8765/docs)

You are now ready to develop locally!

## �� Project Structure

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
