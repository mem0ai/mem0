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
