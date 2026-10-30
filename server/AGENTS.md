# Self-hosted server (`server/`)

FastAPI REST server wrapping the Python SDK. Docker only; there is no local non-Docker path.

## Commands

```bash
# Production image
make build        # docker build -t mem0-api-server .
make run_local    # docker run -p 8000:8000 with .env

# Development stack (FastAPI + PostgreSQL/pgvector + Neo4j)
docker-compose up
```

| Service | Port |
|---------|------|
| mem0 API | 8888 |
| PostgreSQL (pgvector) | 8432 |
| Neo4j HTTP | 8474 |
| Neo4j Bolt | 8687 |

## Conventions

- **Framework:** FastAPI on uvicorn, auto-reload in dev.
- **Stores:** PostgreSQL with the pgvector extension, Neo4j 5.x with the APOC plugin.
- **Hot reload:** the dev Dockerfile mounts both `server/` and `mem0/`, so SDK edits take effect without a rebuild.
- Use Docker Compose for local work. Do not add a "run it with uvicorn directly" path.
- The server imports the Python SDK from the repo, so its conventions apply to any SDK code you touch: see [`../mem0/AGENTS.md`](../mem0/AGENTS.md).

Never commit `.env`. Credentials for the compose services belong in `.env.example` as placeholders only.
