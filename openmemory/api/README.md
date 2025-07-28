# OpenMemory API

This directory contains the backend API for OpenMemory, built with FastAPI and SQLAlchemy. This also runs the Mem0 MCP Server that you can use with MCP clients to remember things.

## Quick Start with Docker (Recommended)

The easiest way to get started is using Docker. Make sure you have Docker and Docker Compose installed.

1. Build the containers:
```bash
make build
```

2. Create `.env` file:
```bash
make env
```

Once you run this command, edit the file `api/.env` and enter the `OPENAI_API_KEY`.

3. Start the services:
```bash
make up
```

The API will be available at `http://localhost:8765`

### Common Docker Commands

- View logs: `make logs`
- Open shell in container: `make shell`
- Run database migrations: `make migrate`
- Run tests: `make test`
- Run tests and clean up: `make test-clean`
- Stop containers: `make down`

## API Documentation

Once the server is running, you can access the API documentation at:
- Swagger UI: `http://localhost:8765/docs`
- ReDoc: `http://localhost:8765/redoc`

## Testing MCP Server

### Using MCP Inspector (Recommended)

The official MCP Inspector tool is the best way to test MCP servers:

```bash
npx @modelcontextprotocol/inspector http://localhost:8765/mcp/cursor/sse/rmatena
```

This provides an interactive interface to test all MCP tools and see the raw protocol messages.

### Using Memory Inspect Tool in Cursor

Alternatively, you can use the built-in Memory Inspect Tool in Cursor IDE:
1. Open Cursor
2. Go to Memory Inspect Tool in the left panel
3. Test your MCP server functions

### Manual Testing

You can also test the MCP server manually using curl:

```bash
# Test SSE connection
curl -N http://localhost:8765/mcp/cursor/sse/rmatena

# Test MCP initialization
curl -X POST http://localhost:8765/mcp/messages/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {"tools": {}},
      "clientInfo": {"name": "cursor", "version": "1.0.0"}
    }
  }'
```

### Automated Testing

Run the automated test suite:

```bash
# Run all tests
make test

# Run specific MCP tests
python tests/test_openmemory_mcp.py

# View test logs
docker-compose logs -f openmemory-mcp
```

## Project Structure

- `app/`: Main application code
  - `models.py`: Database models
  - `database.py`: Database configuration
  - `routers/`: API route handlers
- `migrations/`: Database migration files
- `tests/`: Test files
- `alembic/`: Alembic migration configuration
- `main.py`: Application entry point

## Development Guidelines

- Follow PEP 8 style guide
- Use type hints
- Write tests for new features
- Update documentation when making changes
- Run migrations for database changes
