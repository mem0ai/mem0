# Jean Memory Local Development Guide

This guide explains how to set up and run Jean Memory for local development, optimized for speed and efficiency.

## 🚀 Quick Start

We offer two development approaches:

1. **Hybrid Mode** (Recommended): Backend in Docker, Frontend running locally
   ```bash
   # Start only backend services in Docker and run UI locally
   make backend
   make ui-local
   ```

2. **Full Docker Mode**: All services in Docker (slower for UI development)
   ```bash
   # Start all services in Docker
   make up
   ```

## 🛠️ Setup

First-time setup:

```bash
make setup
```

This will:
- Create necessary environment files
- Build Docker images
- Set up the database
- Install dependencies

## 🧩 Development Workflows

### Recommended Workflow (Hybrid Mode)

For the fastest development experience:

1. Start backend services in Docker:
   ```bash
   make backend
   ```

2. Run the UI locally:
   ```bash
   make ui-local
   ```

This approach gives you:
- Fast UI hot-reloading with Next.js running natively
- Backend services (API, PostgreSQL, Qdrant) running in isolated Docker containers
- Auto-connection between UI and API

### Checking Status

To check the status of all services:

```bash
make status
```

### Stopping Services

To stop all services:

```bash
make down
```

### Viewing Logs

```bash
# View all logs
make logs

# View only API logs
make logs-api
```

## 🔧 Troubleshooting

### UI Issues

If you encounter UI issues:

1. Try clearing the Next.js cache:
   ```bash
   cd ui
   rm -rf .next
   ```

2. Check dependencies:
   ```bash
   cd ui
   npm install --legacy-peer-deps
   ```

3. Make sure your Node.js version is compatible (recommended: v18+)

### Backend Issues

If backend services aren't working:

1. Check Docker status:
   ```bash
   docker ps
   ```

2. Restart backend services:
   ```bash
   make restart-backend
   ```

3. Check logs for errors:
   ```bash
   make logs-api
   ```

## 📝 Notes on Performance

- The UI running locally will be significantly faster than in Docker
- We use an optimized Next.js configuration for local development
- Memory usage is controlled with Node options to prevent crashes
- Turbopack is used when available for faster compilation

## 🔄 Switching Between Modes

You can easily switch between development modes:

- To switch from hybrid to full Docker:
  ```bash
  make down
  make up
  ```

- To switch from full Docker to hybrid:
  ```bash
  make down
  make backend
  make ui-local
  ```

## Prerequisites

- Docker Desktop installed and running
- Python 3.8+ installed
- Node.js and npm installed
- An OpenAI API key

## Architecture

The local development environment consists of:

- **PostgreSQL**: Database for metadata and user data
- **Qdrant**: Vector database for embeddings
- **API**: FastAPI backend service
- **UI**: Next.js frontend application

All services run in Docker containers for consistency.

## Environment Configuration

### API Configuration (`api/.env`)

Key variables:
- `USER_ID`: Your local user ID (automatically set to your system username)
- `DATABASE_URL`: PostgreSQL connection string (pre-configured for Docker)
- `OPENAI_API_KEY`: Your OpenAI API key (required)
- `QDRANT_HOST`: Qdrant hostname (set to `localhost` for local dev)

### UI Configuration (`ui/.env`)

Key variables:
- `NEXT_PUBLIC_API_URL`: API endpoint (http://localhost:8765)
- `NEXT_PUBLIC_USER_ID`: Your local user ID

## Local vs Production

The application automatically detects local development mode when:
- `USER_ID` environment variable is set
- Supabase configuration is missing or empty

In local development mode:
- Authentication is bypassed (no Supabase required)
- A default user and app are created automatically
- All API endpoints accept any token or no token

## Common Commands

```bash
# Start all services
make up

# Stop all services
make down

# View logs
make logs

# Check service status
make status

# Run database migrations
make migrate

# Open shell in API container
make shell

# Run tests
make test

# Clean everything and start fresh
make clean
make setup
```

## Testing

Run the comprehensive test suite:
```bash
python test-local-setup.py
```

This will verify:
- All Docker containers are running
- PostgreSQL is accessible and has correct schema
- Qdrant is accessible
- API is responding
- UI is accessible
- Authentication bypass is working
- Environment is properly configured

## Data Persistence

- PostgreSQL data: Stored in Docker volume `postgres_data`
- Qdrant data: Stored in Docker volume `qdrant_data`
- Data persists between container restarts
- Use `make clean` to remove all data

## Security Notes

- The local setup bypasses authentication for convenience
- Never use local development configuration in production
- Keep your `.env` files out of version control
- The default PostgreSQL password is only for local development 