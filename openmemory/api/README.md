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

## Backup Import Limits

OpenMemory bounds backup imports to avoid excessive memory use from large or highly compressed archives. The defaults are suitable for ordinary local backups:

| Variable | Default | Purpose |
|---|---:|---|
| `OPENMEMORY_BACKUP_READ_CHUNK_BYTES` | `1048576` (1 MiB) | Upload read chunk size |
| `OPENMEMORY_MAX_BACKUP_UPLOAD_BYTES` | `104857600` (100 MiB) | Maximum uploaded `.zip` size |
| `OPENMEMORY_MAX_BACKUP_SQLITE_BYTES` | `10485760` (10 MiB) | Maximum `memories.json` member size |
| `OPENMEMORY_MAX_BACKUP_LOGICAL_GZIP_BYTES` | `104857600` (100 MiB) | Maximum compressed `memories.jsonl.gz` member size |
| `OPENMEMORY_MAX_BACKUP_LOGICAL_DECOMPRESSED_BYTES` | `262144000` (250 MiB) | Maximum decompressed JSONL size |
| `OPENMEMORY_MAX_BACKUP_LOGICAL_RECORD_BYTES` | `1048576` (1 MiB) | Maximum single JSONL record size |
| `OPENMEMORY_MAX_BACKUP_LOGICAL_RECORDS` | `250000` | Maximum JSONL record count |
| `OPENMEMORY_MAX_BACKUP_MANIFEST_RECORDS` | `250000` | Maximum records per `memories.json` list section |
| `OPENMEMORY_MAX_BACKUP_ZIP_MEMBERS` | `64` | Maximum file entries in the uploaded `.zip` |
| `OPENMEMORY_MAX_BACKUP_ZIP_CENTRAL_DIRECTORY_BYTES` | `1048576` (1 MiB) | Maximum ZIP central directory size |

For trusted large restores, raise the relevant value in `api/.env` and restart the API process or container.
These values are read when the API starts.
Oversized imports fail with `413`; malformed zip or JSON content fails with `400` before any import writes begin.

Exports are not size-capped. If an instance exports a very large dataset, restoring that backup on a default-config API may
return `413` until the matching import limits are raised.

OpenMemory is intended for trusted local/self-hosted use. The backup endpoints use the submitted `user_id` to select
export/import data, so do not expose them directly to untrusted networks without an authentication or proxy layer.

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
