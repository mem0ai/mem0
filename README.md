<p align="center">
  <a href="https://github.com/jonathan-politzki/your-memory">
    <img src="docs/images/jean-logo.png" width="300px" alt="Jean Memory - Your Memory, Your AI">
  </a>
</p>

<p align="center">
  <h1 align="center">Your Memory</h1>
  <p align="center">A secure, private memory layer for your AI.</p>
</p>

<p align="center">
  <a href="https://jeanmemory.com">Website</a>
  ·
  <a href="https://jeanmemory.com/dashboard-new">Dashboard</a>
  ·
  <a href="https://jeanmemory.com/api-docs">Docs</a>
  ·
  <a href="https://github.com/jonathan-politzki/your-memory/issues">Report an Issue</a>
</p>

<p align="center">
  <a href="https://github.com/jonathan-politzki/your-memory">
    <img src="https://img.shields.io/github/stars/jonathan-politzki/your-memory?style=social" alt="GitHub stars">
  </a>
  <a href="https://github.com/jonathan-politzki/your-memory/blob/main/LICENSE">
    <img src="https://img.shields.io/github/license/jonathan-politzki/your-memory?style=flat-square&color=blue" alt="License">
  </a>
  <a href="https://github.com/jonathan-politzki/your-memory/issues">
    <img src="https://img.shields.io/github/issues/jonathan-politzki/your-memory?style=flat-square&color=orange" alt="GitHub issues">
  </a>
</p>

## What is Jean Memory?

Jean securely stores the personal context that makes your AI truly yours. From your unique insights to your personal preferences, this is the data that powers a smarter, more helpful AI. You control what's remembered and what's shared, always.

- **🔒 Private & Secure**: Your context is yours alone.
- **🚀 Fast & Universal**: Works across all your MCP-compatible AI tools like Claude and Cursor.
- **🏠 Cloud or Local**: Use our managed service or host it yourself.

🧠 **Human-like Agentic Memory**: Jean is more than just a vector database. It creates a dynamic, connected graph of your memories, allowing AI agents to understand relationships, context, and how ideas evolve over time. This enables more sophisticated reasoning and a deeper understanding of you.

<p align="center">
  <img src="/openmemory/ui/public/og-image.png" width="600px" alt="Jean Memory Knowledge Graph">
</p>

## 🚀 Quick Start

Get started in seconds with our hosted service:

1.  **Sign up** at [jeanmemory.com](https://jeanmemory.com) and go to your dashboard.
2.  **Choose an app** (like Claude or Cursor) and get your install command.
3.  **Run the command** to connect your AI tool.
4.  **Restart your AI app** and start using your memory!

## 🎥 **Video Tutorial**

Watch this 5-minute step-by-step tutorial to get Jean Memory working with your AI tools:

<p align="center">
  <a href="https://youtu.be/qXe4mEaCN9k">
    <img src="https://img.youtube.com/vi/qXe4mEaCN9k/maxresdefault.jpg" alt="Jean Memory Setup Tutorial" width="600">
  </a>
</p>

**[▶️ Watch the Full Tutorial on YouTube](https://youtu.be/qXe4mEaCN9k)**

## 🛠️ Local Development

Run the entire Jean Memory stack on your local machine.

**Prerequisites:**
- Node.js 18+ and npm
- Docker and Docker Compose
- Git

**1. Clone the repository:**
```bash
git clone https://github.com/jonathan-politzki/your-memory.git
cd your-memory
```

**2. Run initial setup:**
This creates environment files and starts all services:
```bash
make setup
```

**3. Add your API keys:**
When prompted during setup, add your API keys:
- `OPENAI_API_KEY` (required) - Get from [OpenAI Platform](https://platform.openai.com/api-keys)
- `GEMINI_API_KEY` (optional) - Get from [Google AI Studio](https://makersuite.google.com/app/apikey)

**4. Build the environment:**
After adding API keys, build the environment:
```bash
make build
```

**5. Start the services:**
You'll need two separate terminals:

*Terminal 1 - Start backend (includes Supabase):*
```bash
make backend
```

*Terminal 2 - Start frontend:*
```bash
make ui-local
```

**3. Access the application:**
- **UI**: `http://localhost:3000`
- **API Docs**: `http://localhost:8765/docs`
- **Supabase Studio**: `http://localhost:54323`

## ⭐ Upgrade to Jean Memory Pro

Advanced features for power users and developers, including **priority support, advanced search, higher limits, and data export.**

<p align="center">
  <a href="https://buy.stripe.com/8x214n2K0cmVadx3pIabK01">
    <img src="https://img.shields.io/badge/⭐_Upgrade_to_Pro-$19%2Fmonth-9333ea?style=for-the-badge&logo=stripe&logoColor=white" alt="Upgrade to Jean Memory Pro">
  </a>
</p>

## 🤝 Contributing

We welcome contributions! Please see our [contributing guide](CONTRIBUTING.md) to get started.

## 📄 License

This project incorporates code from [mem0ai/mem0](https://github.com/mem0ai/mem0) under the Apache 2.0 License. Jean Memory additions and modifications are proprietary.

## 🙋‍♂️ Support

- **Docs**: [jeanmemory.com/api-docs](https://jeanmemory.com/api-docs)
- **Issues**: [GitHub Issues](https://github.com/jonathan-politzki/your-memory/issues)
- **Email**: [jonathan@jeantechnologies.com](mailto:jonathan@jeantechnologies.com)

---

<p align="center">
  Built with ❤️ by <a href="https://jeantechnologies.com">Jean Technologies</a>
</p>
