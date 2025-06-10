# Jean Memory Local Development Guide

## Overview

Jean Memory supports three different development setups:

1. **Fully Local Docker Setup** - Uses PostgreSQL and Qdrant running in Docker containers
2. **Hybrid Cloud Setup** - Uses Supabase (cloud) for database and Qdrant Cloud for vector storage
3. **Production Setup** - Deployed on Render with Supabase

## Current Implementation Status

### ✅ What's Working

- **Local Authentication Bypass**: When `USER_ID` environment variable is set, the system bypasses Supabase authentication
- **Docker Compose**: Sets up local PostgreSQL and Qdrant containers
- **Multiple Setup Scripts**: Different scripts for different deployment scenarios
- **Environment Management**: Scripts to manage and backup environment configurations
- **Centralized Configuration**: New `config.py` module handles local vs production settings
- **Database Initialization**: Automatic setup of tables and default data for local development
- **Complete Schema**: Full database schema including all tables and indexes

### ✅ Fixed Issues

1. **Missing .env.template**: Now created by `fix-local-setup.sh`
2. **Database Schema**: Complete schema with all tables is now included
3. **Configuration Management**: Centralized config module handles environment detection
4. **Authentication**: Consistent auth handling between frontend and backend

## Setup Options

### Option 1: Fully Local Docker Setup (Recommended for Development)

This setup runs everything locally using Docker containers.

#### Prerequisites
- Docker and Docker Compose
- Python 3.8+
- Node.js 14+
- npm or pnpm

#### Steps

1. **Run the fix script first** (this creates missing files):
   ```bash
   ./fix-local-setup.sh
   ```

2. **Edit the .env file** and add your OpenAI API key:
   ```bash
   # Edit /Users/rohankatakam/Documents/for/your-memory/.env
   # Replace 'your-openai-api-key-here' with your actual key
   ```

3. **Start Docker containers**:
   ```bash
   ./setup-local-dev.sh --fresh
   ```

4. **Initialize the database** (after Docker starts):
   ```bash
   ./init-local-database.sh
   ```

5. **Complete the setup**:
   ```bash
   ./setup-local-dev.sh
   ```

6. **Start the services**:
   ```bash
   # Terminal 1 - Start API
   ./start-api.sh
   
   # Terminal 2 - Start UI
   ./start-ui.sh
   ```

7. **Access the application**:
   - API: http://localhost:8765
   - UI: http://localhost:3000
   - PostgreSQL: localhost:5432 (user: jean_memory, password: memory_password)
   - Qdrant UI: http://localhost:6334

8. **Verify the setup** (optional but recommended):
   ```bash
   ./test-complete-local-setup.py
   ```

### Option 2: Hybrid Cloud Setup (Supabase + Qdrant Cloud)

This setup uses cloud services for data storage while running the application locally.

#### Prerequisites
- Supabase account and project
- Qdrant Cloud account
- Python 3.8+
- Node.js 14+

#### Steps

1. **Create .env from template**:
   ```bash
   cp .env.template .env
   ```

2. **Edit .env with your cloud credentials**:
   - Supabase URL, Anon Key, and Service Key
   - Qdrant Cloud host and API key
   - OpenAI API key

3. **Run the hybrid setup**:
   ```bash
   ./setup-hybrid.sh
   ```

4. **Start the services**:
   ```bash
   # Using jean-memory.sh
   ./jean-memory.sh start
   
   # Or manually:
   # Terminal 1
   ./jean-memory.sh start-api
   
   # Terminal 2
   ./jean-memory.sh start-ui
   ```

### Option 3: Using the Unified Management Script

The `jean-memory.sh` script provides a unified interface for managing the environment.

```bash
# Setup new environment
./jean-memory.sh setup

# Test connections
./jean-memory.sh test-connection

# Install dependencies
./jean-memory.sh setup-deps

# Start services
./jean-memory.sh start

# Check status
./jean-memory.sh status

# Stop services
./jean-memory.sh stop
```

## Environment Variables

### Required for All Setups
- `OPENAI_API_KEY`: Your OpenAI API key

### Local Docker Setup
- `USER_ID`: Set to `default_user` for local auth bypass
- `DATABASE_URL`: PostgreSQL connection string (auto-configured)
- `QDRANT_HOST`: Set to `localhost`
- `QDRANT_PORT`: Set to `6333`

### Hybrid/Production Setup
- `SUPABASE_URL`: Your Supabase project URL
- `SUPABASE_ANON_KEY`: Supabase anonymous key
- `SUPABASE_SERVICE_KEY`: Supabase service key
- `QDRANT_HOST`: Qdrant Cloud host
- `QDRANT_API_KEY`: Qdrant Cloud API key

## Troubleshooting

### Docker Issues
- **Containers not starting**: Check if ports 5432, 6333, 6334 are already in use
- **Database connection failed**: Wait for PostgreSQL to be ready before running migrations

### Authentication Issues
- **401 Unauthorized**: Make sure `USER_ID=default_user` is set in the API .env file
- **Frontend auth errors**: Check that `NEXT_PUBLIC_USER_ID=default_user` is in UI .env.local

### Database Issues
- **Migration failures**: Run `./init-local-database.sh` to initialize the schema
- **Qdrant errors**: Check if Qdrant container is running and accessible

### Common Commands

```bash
# Check Docker containers
docker ps

# View Docker logs
docker-compose logs -f

# Reset everything
./setup-local-dev.sh --fresh

# Clean up Docker volumes
docker-compose down -v

# Check API logs
tail -f openmemory/api/logs/*.log

# Test local auth
./test-local-auth.py
```

## Architecture Decisions

1. **Local Auth Bypass**: The `local_auth.py` module provides a mock Supabase user when `USER_ID` is set
2. **Database Flexibility**: Supports both local PostgreSQL and Supabase cloud database
3. **Vector Storage**: Can use either local Qdrant or Qdrant Cloud
4. **Environment Isolation**: Separate .env files for root, API, and UI components

## Testing Your Setup

After completing the setup, you can verify everything is working correctly:

```bash
# Run the comprehensive test suite
./test-complete-local-setup.py

# Or test individual components:

# Test local authentication
./test-local-auth.py

# Test database connection
docker exec jeanmemory_postgres_service pg_isready -U jean_memory

# Test Qdrant
curl http://localhost:6334/collections

# Test API
curl http://localhost:8765/health
```

## Configuration Details

### Environment Detection

The system automatically detects local development mode when:
- `USER_ID` environment variable is set in the API
- `NEXT_PUBLIC_USER_ID` is set in the UI

### Database Schema

The complete schema includes:
- `users` - User accounts
- `apps` - Applications owned by users
- `memories` - Core memory storage
- `categories` - Memory categorization
- `documents` - Document storage
- `document_chunks` - Document chunking for processing
- `access_controls` - Permission management
- `archive_policies` - Archival rules
- `memory_status_history` - State change tracking
- `memory_access_logs` - Access logging

### API Configuration Module

The new `config.py` module provides:
- Centralized configuration management
- Environment detection (`is_local_development`)
- Validation of required settings
- Safe defaults for local development

## Next Steps for Improvement

1. **Create proper Alembic migrations** for database versioning
2. **Add Docker health checks** for better container management
3. **Create development fixtures** for testing with sample data
4. **Add API documentation** for local development endpoints
5. **Implement hot-reloading** for faster development cycles
6. **Create development dashboard** for monitoring local services 