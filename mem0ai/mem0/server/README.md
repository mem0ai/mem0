# Mem0 REST API Server

Mem0 provides a REST API server (written using FastAPI). Users can perform all operations through REST endpoints. The API also includes OpenAPI documentation, accessible at `/docs` when the server is running.

## Features

- **Create memories:** Create memories based on messages for a user, agent, or run.
- **Retrieve memories:** Get all memories for a given user, agent, or run.
- **Search memories:** Search stored memories based on a query.
- **Update memories:** Update an existing memory.
- **Delete memories:** Delete a specific memory or all memories for a user, agent, or run.
- **Reset memories:** Reset all memories for a user, agent, or run.
- **OpenAPI Documentation:** Accessible via `/docs` endpoint.

## Local Embeddings (Default)

Mem0 now uses local embeddings via [sentence-transformers](https://www.sbert.net/) by default (model: `all-MiniLM-L6-v2`). No OpenAI API key is required to run the server.

To install dependencies:

```
pip install -r server/requirements.txt
```

To use a different embedding model, edit the `DEFAULT_CONFIG` in `server/main.py` and set the desired model name in the embedder config (see [available models](https://www.sbert.net/docs/pretrained_models.html)).

## Running the server

Follow the instructions in the [docs](https://docs.mem0.ai/open-source/features/rest-api) to run the server.
