# 🧠 OpenMemory

An intelligent personal knowledge management system that helps you capture, organize, and retrieve information using AI-powered search and memory.

## ✨ Features

- **Smart Document Processing**: Upload and automatically process PDFs, text files, and web content
- **AI-Powered Search**: Find information using natural language queries
- **Memory System**: Build a persistent knowledge base that grows with your usage
- **Multi-Modal Support**: Handle text, documents, and web content seamlessly
- **Local Development**: Complete production-parity development environment

## 🚀 Quick Start

### Prerequisites

- **Node.js 18+** - [Download](https://nodejs.org/)
- **Python 3.8+** - [Download](https://python.org/)
- **Docker Desktop** - [Download](https://docker.com/products/docker-desktop)
- **OpenAI API Key** - [Get one](https://platform.openai.com/api-keys)

### One-Command Setup

```bash
# 1. Clone the repository
git clone <repository-url>
cd your-memory/openmemory

# 2. Run the setup script (only requires your OpenAI API key!)
make setup

# 3. Start developing
make dev
```

That's it! The setup script will:
- Install all dependencies automatically
- Start local Supabase (database + auth)
- Configure vector database (Qdrant)
- Set up environment with your API key
- Launch the development servers

### What You Get

| Service | URL | Description |
|---------|-----|-------------|
| **UI** | http://localhost:3000 | Next.js frontend |
| **API** | http://localhost:8765 | FastAPI backend |
| **Supabase Studio** | http://localhost:54323 | Database admin |
| **Qdrant Dashboard** | http://localhost:6333/dashboard | Vector database |

## 🛠️ Development Commands

```bash
# Development
make dev          # Start complete environment
make dev-api      # Start only API server  
make dev-ui       # Start only UI server
make stop         # Stop all services
make restart      # Restart everything
make status       # Check what's running

# Database
make migrate      # Apply database migrations
make db-reset     # Reset database
make studio       # Open Supabase Studio

# Utilities  
make logs         # View service logs
make test         # Run tests
make clean        # Reset everything
```

## 🏗️ Architecture

OpenMemory uses a modern, production-ready architecture:

- **Frontend**: Next.js with TypeScript
- **Backend**: FastAPI with Python
- **Database**: PostgreSQL via Supabase
- **Vector Store**: Qdrant for embeddings
- **Authentication**: Supabase Auth
- **AI**: OpenAI GPT models + embeddings

### Local Development Benefits

✅ **Production Parity**: Same services as production  
✅ **Real Authentication**: No auth bypass - test real flows  
✅ **Persistent Data**: Data persists across sessions  
✅ **Isolated Environment**: Never affects production  
✅ **One-Command Setup**: Minimal configuration required  

## 📊 Usage

### Creating Your First Memory

1. Open http://localhost:3000
2. Sign up with your email
3. Upload a document or add text content
4. Ask questions about your content using natural language

### Document Processing

```python
# Upload a PDF
POST /api/documents/upload
Content-Type: multipart/form-data

# The system will:
# 1. Extract text from the PDF
# 2. Split into chunks
# 3. Generate embeddings
# 4. Store in vector database
# 5. Make searchable via AI
```

### AI-Powered Search

```python
# Search your knowledge base
POST /api/search
{
  "query": "What did the document say about machine learning?",
  "limit": 5
}

# Returns relevant chunks with context
```

## 🔧 Configuration

The setup is designed to work out-of-the-box with minimal configuration:

### Required (Auto-prompted during setup)
- `OPENAI_API_KEY` - Your OpenAI API key

### Optional
- `GEMINI_API_KEY` - Google's Gemini API (recommended)

### Auto-Generated
All other configuration (database URLs, auth keys, etc.) is automatically generated during setup.

## 🧪 Testing

```bash
# Run all tests
make test

# API tests only
cd api && python -m pytest tests/ -v

# UI tests only  
cd ui && npm test
```

## 📚 API Documentation

Once running, visit http://localhost:8765/docs for interactive API documentation.

## 🔄 Production Deployment

The local development environment mirrors production exactly:

| Component | Local | Production |
|-----------|-------|------------|
| Database | Local Supabase | Supabase Cloud |
| Auth | Local Supabase Auth | Supabase Cloud |
| Vector DB | Docker Qdrant | Qdrant Cloud |
| API | Local FastAPI | Render/Cloud |
| UI | Local Next.js | Vercel/Cloud |

## 🤝 Contributing

1. Run `make setup` to set up your environment
2. Create a feature branch
3. Make your changes
4. Test with `make test`
5. Submit a pull request

The streamlined setup ensures all contributors have identical environments!

## 📖 Documentation

- [Local Development Guide](./LOCAL_DEVELOPMENT.md) - Detailed setup and usage
- [API Documentation](./api/README.md) - Backend API reference
- [Database Schema](./supabase/migrations/) - Database structure
- [Architecture Overview](./ARCHITECTURE.md) - System design

## 📄 License

See [LICENSE](./LICENSE) for details.

---

**Need help?** Check the [troubleshooting guide](./LOCAL_DEVELOPMENT.md#troubleshooting) or open an issue.
