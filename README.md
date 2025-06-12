<p align="center">
  <a href="https://github.com/jonathan-politzki/your-memory">
    <img src="docs/images/jean-logo.png" width="300px" alt="Jean Memory - Your Personal Memory Layer for AI">
  </a>
</p>

<p align="center">
  <h1 align="center">Jean Memory</h1>
  <p align="center">Your Personal Memory Layer for AI Applications, powered by the community.</p>
</p>

<p align="center">
  <a href="https://jeanmemory.com">Learn more</a>
  ·
  <a href="https://app.jeanmemory.com">Try Jean Memory</a>
  ·
  <a href="https://api.jeanmemory.com/docs">API Docs</a>
  ·
  <a href="/openmemory">OpenMemory</a>
</p>

<p align="center">
  <a href="https://github.com/jonathan-politzki/your-memory">
    <img src="https://img.shields.io/github/stars/jonathan-politzki/your-memory?style=social" alt="GitHub stars">
  </a>
  <a href="https://github.com/jonathan-politzki/your-memory">
    <img src="https://img.shields.io/github/forks/jonathan-politzki/your-memory?style=social" alt="GitHub forks">
  </a>
  <a href="https://github.com/jonathan-politzki/your-memory">
    <img src="https://img.shields.io/github/commit-activity/m/jonathan-politzki/your-memory?style=flat-square" alt="GitHub commit activity">
  </a>
  <a href="https://github.com/jonathan-politzki/your-memory/blob/main/LICENSE">
    <img src="https://img.shields.io/github/license/jonathan-politzki/your-memory?style=flat-square&color=blue" alt="License">
  </a>
  <a href="https://github.com/jonathan-politzki/your-memory/issues">
    <img src="https://img.shields.io/github/issues/jonathan-politzki/your-memory?style=flat-square&color=orange" alt="GitHub issues">
  </a>
</p>

<p align="center">
  <strong>🔒 Private • 🚀 Fast • 🔗 Universal</strong>
</p>

## 🚀 What is Jean Memory?

Jean Memory is your **secure, unified memory layer** that works across all AI applications. It gives your AI assistants the ability to remember you, your preferences, and your context - while keeping everything private and under your control.

## 🧠 How Jean Memory Works

<p align="center">
  <img src="docs/images/jean-memory-architecture.png" width="600px" alt="Jean Memory Architecture - Connected Memory Graph">
</p>

Jean Memory creates a **connected memory graph** that links all your AI interactions across different applications. As shown in the diagram above:

- **🎯 Central Memory Hub**: Your personal memory sits at the center, accessible by all connected AI applications
- **🔗 Cross-Application Links**: Memories flow seamlessly between Claude, Cursor, GPT, and other AI tools
- **📊 Smart Connections**: Related memories are automatically linked and surfaced when relevant
- **🔒 Private & Secure**: All connections happen through your personal memory layer - no data sharing between AI providers
- **⚡ Real-time Sync**: Updates to your memory are instantly available across all connected applications

This means when you tell Claude about your coding preferences, Cursor automatically knows them too. When you research a topic in one app, that context is available everywhere.

### Why Jean Memory?

- **🔒 Privacy First**: Your memories stay yours with end-to-end encryption
- **⚡ Lightning Fast**: Instant access to your context across all AI tools  
- **🌐 Universal**: Works with Claude, GPT, Cursor, and any MCP-compatible app
- **🏠 Your Choice**: Use our hosted service or run it completely locally

### Key Features

**Core Capabilities:**
- **Cross-Application Memory**: Seamlessly share context between Claude, Cursor, GPT, and more
- **MCP Protocol**: Built on the Model Context Protocol for maximum compatibility
- **Local & Cloud Options**: Choose between our hosted service or complete local deployment
- **Developer-Friendly**: Simple APIs and one-command setup

**Use Cases:**
- **Personal AI Assistant**: Remember your preferences across all AI interactions
- **Development Work**: Maintain context across coding sessions in different tools
- **Research & Writing**: Keep track of insights and references across platforms
- **Customer Support**: Build AI that remembers customer history and preferences

## 🚀 Quick Start

### Option 1: Hosted Service (Recommended)

Get started in seconds with our hosted service:

1. **Sign up** at [jeanmemory.com](https://jeanmemory.com)
2. **Get your install command** from the dashboard
3. **Run one command** to connect your AI tools:

```bash
npx install-mcp https://api.jeanmemory.com/mcp/claude/sse/your-user-id --client claude
```

4. **Restart your AI app** and start using memory!

## 🎥 **Video Tutorial**

Watch this 5-minute step-by-step tutorial to get Jean Memory working with your AI tools:

<p align="center">
  <a href="https://youtu.be/qXe4mEaCN9k">
    <img src="https://img.youtube.com/vi/qXe4mEaCN9k/maxresdefault.jpg" alt="Jean Memory Setup Tutorial" width="600">
  </a>
</p>

**[▶️ Watch the Full Tutorial on YouTube](https://youtu.be/qXe4mEaCN9k)**

*Perfect for beginners! Covers everything from installing Node.js to testing your first memory.*

### Option 2: Local Development

Set up and run Jean Memory on your local machine for development. For a detailed guide, please see the [local development README](/openmemory/README.md).

**1. Clone the repository:**
```bash
git clone https://github.com/jonathan-politzki/your-memory.git
cd your-memory
```

**2. Run initial setup:**
This command creates your environment files.
```bash
make setup
```

**3. Add API Keys:**
Edit `openmemory/api/.env` and add your `OPENAI_API_KEY` and `GEMINI_API_KEY`.

**4. Build the environment:**
This installs dependencies and builds the Docker containers.
```bash
make build
```

**5. Start the services:**
You'll need two separate terminals for this.

*In terminal 1, start the backend:*
```bash
make backend
```

*In terminal 2, start the frontend:*
```bash
make ui-local
```

**6. Access the application:**
- **UI**: `http://localhost:3000`
- **API Docs**: `http://localhost:8765/docs`

## ⭐ Upgrade to Jean Memory Pro

Take your AI memory to the next level with **Jean Memory Pro** - advanced features for power users and developers who demand more from their AI tools.

### 🚀 Pro Features

- **🎯 Priority Support** - Get help fast with dedicated support channels and faster response times
- **💡 Feature Requests** - Request new features and vote on development priorities to shape the roadmap
- **🔍 Advanced Search** - Semantic search, date filters, smart categorization, and memory insights
- **📈 Higher Limits** - 10x more memories, API calls, and storage vs. free tier
- **📦 Data Export** - Download and backup all your memories in multiple formats anytime
- **🚪 Early Access** - Get beta features and improvements weeks before general release  
- **🏷️ Custom Categories** - Organize memories with personalized tags, folders, and smart grouping
- **⚡ Bulk Operations** - Manage hundreds of memories with powerful batch editing and organization tools

<p align="center">
  <a href="https://buy.stripe.com/fZuaEX70gev399t4tMabK00">
    <img src="https://img.shields.io/badge/⭐_Upgrade_to_Pro-$19.99-9333ea?style=for-the-badge&logo=stripe&logoColor=white" alt="Upgrade to Jean Memory Pro">
  </a>
</p>

**[→ Upgrade to Jean Memory Pro for $19.99](https://buy.stripe.com/fZuaEX70gev399t4tMabK00)**

Join hundreds of developers and power users building the future of AI memory management! 🚀

## 💬 Example Usage

Once connected, you can:

```
You: "Remember that I prefer TypeScript over JavaScript for new projects"
AI: ✓ I'll remember your preference for TypeScript.

You: "Help me set up a new web project"  
AI: I'll help you create a TypeScript project since you prefer TypeScript over JavaScript...
```

Your AI will remember this across all applications - Claude, Cursor, GPT, and more!

## 🔗 Supported Applications

Jean Memory works with any MCP-compatible application:

- **Claude Desktop** - Anthropic's AI assistant
- **Cursor** - AI-powered code editor  
- **Windsurf** - Codeium's AI editor
- **Cline** - VS Code AI extension
- **Any MCP Client** - Universal compatibility

## 🛠️ For Developers

### API Integration

```python
import requests

# Add a memory
response = requests.post("https://api.jeanmemory.com/memories", 
    headers={"Authorization": "Bearer your-api-key"},
    json={"text": "User prefers dark mode", "user_id": "user123"}
)

# Search memories  
response = requests.get("https://api.jeanmemory.com/memories/search",
    params={"query": "dark mode", "user_id": "user123"},
    headers={"Authorization": "Bearer your-api-key"}
)
```

### MCP Integration

Jean Memory is built on the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/), making it compatible with any MCP-supporting application.

### Local Deployment

Full docker-compose setup included for local development and self-hosting.

## 🏗️ Architecture

Jean Memory consists of:

- **Memory API** - Core memory storage and retrieval
- **MCP Server** - Model Context Protocol compatibility  
- **Web UI** - Dashboard for managing memories
- **Vector Database** - Semantic search capabilities
- **Authentication** - Secure user management

## 📚 Documentation

- **Getting Started**: [jeanmemory.com/docs](https://jeanmemory.com/docs)
- **API Reference**: [api.jeanmemory.com/docs](https://api.jeanmemory.com/docs)
- **MCP Setup**: [Local setup guide](/openmemory/README.md)

## 🤝 Contributing

We welcome contributions! Jean Memory is built on open source foundations and we believe in community-driven development.

### How to Contribute

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Commit your changes**: `git commit -m 'Add amazing feature'`
4. **Push to branch**: `git push origin feature/amazing-feature`
5. **Open a Pull Request**
6. **⭐ [Support the project](https://buy.stripe.com/fZuaEX70gev399t4tMabK00)** ($19.99) - Help fund development

### Development Setup

```bash
git clone https://github.com/jonathan-politzki/your-memory.git
cd your-memory
# See /openmemory/README.md for detailed setup
```

## 🔒 Privacy & Security

- **End-to-end encryption** available for sensitive data
- **Local deployment** option for complete control
- **No vendor lock-in** - export your data anytime
- **Transparent** - open source components you can audit

## 📈 Roadmap

- [x] **MCP Protocol Support** - Universal AI app compatibility
- [x] **Hosted Service** - Managed cloud offering
- [x] **Local Deployment** - Self-hosting capabilities
- [ ] **Client-side Encryption** - Zero-knowledge architecture
- [ ] **Advanced Search** - Semantic and temporal queries
- [ ] **Team Collaboration** - Shared memory spaces
- [ ] **Enterprise Features** - SSO, compliance, analytics

## 📄 License

This project incorporates code from [mem0ai/mem0](https://github.com/mem0ai/mem0) under the Apache 2.0 License.

Jean Memory additions and modifications are proprietary. See [LICENSE-JEAN.md](/openmemory/LICENSE-JEAN.md) for details.

## 🙋‍♂️ Support

- **Documentation**: [jeanmemory.com/docs](https://jeanmemory.com/docs)
- **Issues**: [GitHub Issues](https://github.com/jonathan-politzki/your-memory/issues)
- **Upgrade to Pro**: [Jean Memory Pro](https://buy.stripe.com/fZuaEX70gev399t4tMabK00) ($19.99)
- **Email**: [jonathan@jeantechnologies.com](mailto:jonathan@jeantechnologies.com)

---

## ⭐ Star History

<p align="center">
  <a href="https://star-history.com/#jonathan-politzki/your-memory&Date">
    <img src="https://api.star-history.com/svg?repos=jonathan-politzki/your-memory&type=Date" alt="Star History Chart">
  </a>
</p>

---

<p align="center">
  Built with ❤️ by <a href="https://jeantechnologies.com">Jean Technologies</a>
</p>