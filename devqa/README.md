# SingleStore DevQA Testing

End-to-end testing of the mem0 SingleStore connector against a real SingleStore instance.

## Prerequisites

- Docker (for local SingleStore) or a remote SingleStore instance
- Python 3.9+
- An OpenAI API key (for embeddings)

## Quick Start (Remote SingleStore)

```bash
# 1. Set credentials
export SINGLESTORE_HOST=your-host.svc.singlestore.com
export SINGLESTORE_PORT=3306
export SINGLESTORE_USER=admin
export SINGLESTORE_PASSWORD=your-password
export SINGLESTORE_DATABASE=mem0db
export OPENAI_API_KEY=sk-...

# 2. Install deps
pip install -e .. singlestoredb openai

# 3. Run the end-to-end test
python test_e2e.py
```

## Quick Start (Local SingleStore)

```bash
# 1. Start SingleStore
cd devqa
docker compose up -d

# 2. Wait ~15 seconds for SingleStore to initialize
export SINGLESTORE_PASSWORD=testpassword
export OPENAI_API_KEY=sk-...

# 3. Install deps and run
pip install -e .. singlestoredb openai
python test_e2e.py

# 4. Tear down
docker compose down -v
```

## What's Tested

| Test | Description |
|------|-------------|
| Add | Insert memories from a conversation |
| Search | Vector similarity search with user_id filter |
| Get All | List all memories for a user |
| Update | Modify an existing memory |
| History | Retrieve change history for a memory |
| Delete | Remove a specific memory |
| Reset | Drop and recreate the collection |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SINGLESTORE_HOST` | `127.0.0.1` | SingleStore host |
| `SINGLESTORE_PORT` | `3306` | SingleStore port |
| `SINGLESTORE_USER` | `root` | Database user |
| `SINGLESTORE_PASSWORD` | (required) | Database password |
| `SINGLESTORE_DATABASE` | `mem0db` | Database name |
| `OPENAI_API_KEY` | (required) | OpenAI API key for embeddings |
