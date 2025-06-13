# OpenMemory Local Development Guide

This guide explains how to set up and run OpenMemory for local development using Supabase CLI for complete production parity.

## 🏗️ Architecture Overview

Our new local development setup provides **complete production parity** by using:

- **Supabase CLI**: Complete local Supabase instance (Auth, Database, Storage)
- **Qdrant Docker**: Vector database for embeddings
- **Native API & UI**: Fast development with hot-reload

### Why This Approach?

✅ **Production Parity**: Same services as production, just running locally  
✅ **Real Authentication**: No more auth bypass - test real flows  
✅ **Persistent Data**: Your local data persists across sessions  
✅ **Isolated Environment**: Never affects production data  
✅ **Simplified Setup**: One-time setup, then just `make dev`  

## 🚀 Quick Start

### First-Time Setup

```bash
# 1. Clone the repository
git clone <repository-url>
cd your-memory/openmemory

# 2. Run the automated setup script
./scripts/setup-dev-environment.sh
```

The setup script will:
- Check prerequisites (Node.js, Python, Docker)
- Install Supabase CLI
- Create environment configuration
- Start local Supabase
- Configure authentication keys
- Start Qdrant vector database

### Daily Development

After initial setup, just run:

```bash
make dev      # Start everything
make stop     # Stop everything
make status   # Check what's running
```

## 📋 Prerequisites

Before running the setup, ensure you have:

- **Node.js 18+** - [Download](https://nodejs.org/)
- **Python 3.8+** - [Download](https://python.org/)
- **Docker Desktop** - [Download](https://docker.com/products/docker-desktop)
- **OpenAI API Key** - [Get one](https://platform.openai.com/api-keys)

## 🔧 Manual Setup (Alternative)

If you prefer manual setup:

### 1. Install Dependencies

```bash
# Install Supabase CLI
npm install

# Create environment file
cp env.local.example .env.local
```

### 2. Configure Environment

Edit `.env.local` with your OpenAI API key:

```bash
OPENAI_API_KEY=your_openai_api_key_here
```

### 3. Start Services

```bash
# Start Supabase
npx supabase start

# Copy the output keys to .env.local:
# NEXT_PUBLIC_SUPABASE_URL=http://127.0.0.1:54321
# NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon-key>
# SUPABASE_SERVICE_KEY=<service-key>

# Start Qdrant
docker-compose up -d qdrant_db

# Start API
cd api && python -m uvicorn main:app --reload --port 8765

# Start UI
cd ui && npm run dev
```

## 🌐 Available Services

Once running, you'll have access to:

| Service | URL | Description |
|---------|-----|-------------|
| **UI** | http://localhost:3000 | Next.js frontend |
| **API** | http://localhost:8765 | FastAPI backend |
| **Supabase Studio** | http://localhost:54323 | Database admin panel |
| **Qdrant Dashboard** | http://localhost:6333/dashboard | Vector database UI |

## 🔑 Authentication Setup

### Local User Creation

With the new setup, you'll need to create users through the actual Supabase Auth system:

1. **Open UI**: Navigate to http://localhost:3000
2. **Sign Up**: Use the sign-up form to create a test account
3. **Verify Email**: Check the Supabase Inbucket at http://localhost:54324
4. **Sign In**: Use your new account to access the application

### Testing Different Users

You can create multiple test accounts to test different user scenarios:

```bash
# View all local users in Supabase Studio
open http://localhost:54323
# Navigate to Authentication > Users
```

## 🗄️ Database Management

### Migrations

The database schema is managed by Supabase migrations:

```bash
# Apply migrations
make migrate

# Reset database to fresh state
make db-reset

# View database logs
make db-logs
```

### Database Access

```bash
# Connect to local PostgreSQL
psql postgresql://postgres:postgres@localhost:54322/postgres

# Or use Supabase Studio
make studio
```

### Seed Data

Create seed data by:
1. Using the application normally to create content
2. Or adding SQL seed files to `supabase/seed.sql`

## 🔍 Vector Database (Qdrant)

Qdrant runs separately for vector operations:

```bash
# View collections
curl http://localhost:6333/collections

# Dashboard
open http://localhost:6333/dashboard
```

## 🧪 Testing

```bash
# Run all tests
make test

# Run specific test file
cd api && python -m pytest tests/test_auth.py

# Run with coverage
cd api && python -m pytest --cov=app tests/
```

## 🔧 Useful Commands

```bash
# Development
make dev          # Start everything
make stop         # Stop everything  
make restart      # Restart everything
make status       # Check service status

# Database
make migrate      # Apply migrations
make db-reset     # Reset database
make db-logs      # View DB logs

# Tools
make studio       # Open Supabase Studio
make logs         # View all logs
make clean        # Reset everything
make env          # Show configuration
```

## 🐛 Troubleshooting

### "Supabase not running"

```bash
# Check if Docker is running
docker ps

# Restart Supabase
npx supabase stop
npx supabase start
```

### "Port already in use"

```bash
# Find what's using the port
lsof -i :54321

# Kill the process
kill -9 <PID>
```

### "Authentication failed"

1. Check `.env.local` has correct Supabase keys
2. Ensure Supabase is running: `npx supabase status`
3. Try resetting: `make clean` then `make dev`

### "Database connection failed"

```bash
# Check database status
npx supabase status

# Reset database
make db-reset
```

### "Missing API key"

Edit `.env.local` and add your OpenAI API key:
```bash
OPENAI_API_KEY=sk-your-key-here
```

## 📊 Performance Tips

### Faster Startup

After initial setup, subsequent starts are much faster:
- Supabase CLI caches Docker images
- Database data persists between sessions
- Only API/UI need to restart

### Resource Usage

The new setup is more efficient:
- Single PostgreSQL instance (vs separate Docker container)
- Shared Supabase services
- Only Qdrant runs in Docker

### Development Workflow

```bash
# Daily routine
make dev      # Start everything (30 seconds)
# ... develop ...
make stop     # Stop everything (5 seconds)

# When switching branches
make db-reset  # Reset DB if schema changed
make dev       # Restart
```

## 🔄 Data Persistence

### What Persists

- **Database**: All data persists across restarts
- **Auth Users**: Test accounts remain
- **Vector Data**: Qdrant collections persist

### Clean Slate

```bash
make clean  # Removes ALL data, starts fresh
```

## 🚢 Production Comparison

| Feature | Local Development | Production |
|---------|------------------|------------|
| **Database** | Local PostgreSQL (Supabase CLI) | Render PostgreSQL |
| **Auth** | Local Supabase Auth | Supabase Cloud |
| **Storage** | Local Supabase Storage | Supabase Cloud |
| **Vector DB** | Docker Qdrant | Qdrant Cloud |
| **API** | Local FastAPI | Render FastAPI |
| **UI** | Local Next.js | Render Next.js |

**Key Benefit**: Same authentication flows, database schema, and API behavior in both environments!

## 📚 Next Steps

- [API Documentation](./api/README.md)
- [UI Development](./ui/README.md)
- [Database Schema](./supabase/migrations/)
- [Deployment Guide](../DEPLOYMENT_GUIDE.md)

## 🤝 Contributing

1. Fork the repository
2. Run `./scripts/setup-dev-environment.sh`
3. Create your feature branch
4. Make your changes
5. Test locally with `make test`
6. Submit a pull request

The new development setup ensures your local environment matches production exactly, reducing "works on my machine" issues significantly! 