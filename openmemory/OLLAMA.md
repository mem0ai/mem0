# Ollama Integration Guide

This guide shows how to switch OpenMemory from OpenAI to Ollama for local AI processing.

## Prerequisites

### 1. Install Ollama

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Verify installation
ollama --version
```

### 2. Pull Required Models

```bash
# Pull LLM model (for memory processing)
ollama pull mistral:7b-instruct-q4_K_M

# Pull embedding model (for vector search)
ollama pull nomic-embed-text:latest

# Verify models are downloaded
ollama list
```

Expected output:
```
NAME                            SIZE
mistral:7b-instruct-q4_K_M     4.1 GB
nomic-embed-text:latest        274 MB
```

## Configuration Steps

### Step 1: Start OpenMemory

```bash
cd openmemory
docker-compose up -d

# Wait for services to be healthy
sleep 30
```

### Step 2: Stop API Container

```bash
docker-compose stop openmemory-mcp
```

### Step 3: Recreate Qdrant Collections

**Critical:** OpenAI embeddings are 1536 dimensions, Ollama's nomic-embed-text is 768 dimensions.

```bash
# Delete existing collection
curl -X DELETE "http://localhost:6333/collections/openmemory"

# Create collection with correct dimensions for Ollama
curl -X PUT "http://localhost:6333/collections/openmemory" \
  -H "Content-Type: application/json" \
  -d '{
    "vectors": {
      "size": 768,
      "distance": "Cosine"
    }
  }'

# Verify
curl -s "http://localhost:6333/collections/openmemory" | jq '.result.config.params.vectors.size'
# Should output: 768
```

### Step 4: Start API Container

```bash
docker-compose start openmemory-mcp

# Wait for startup
sleep 10
```

### Step 5: Update LLM Configuration

```bash
curl -X PUT "http://localhost:8765/api/v1/config/mem0/llm" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "ollama",
    "config": {
      "model": "mistral:7b-instruct-q4_K_M",
      "temperature": 0.1,
      "max_tokens": 2000,
      "ollama_base_url": "http://host.docker.internal:11434"
    }
  }'
```

### Step 6: Update Embedder Configuration

```bash
curl -X PUT "http://localhost:8765/api/v1/config/mem0/embedder" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "ollama",
    "config": {
      "model": "nomic-embed-text:latest",
      "ollama_base_url": "http://localhost:11434"
    }
  }'
```

### Step 7: Verify Configuration

```bash
# Check providers are set to ollama
curl -s "http://localhost:8765/api/v1/config/" | jq '{llm: .mem0.llm.provider, embedder: .mem0.embedder.provider}'
```

Expected output:
```json
{
  "llm": "ollama",
  "embedder": "ollama"
}
```

## Testing

### Test Memory Creation

```bash
# Create a test memory
curl -X POST "http://localhost:8765/api/v1/memories/" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "text": "I prefer using Ollama for local AI processing"}' | jq .
```

**Note:** First memory may take 4-5 seconds (model loading). Subsequent ones are faster (~2-3s).

### Test Memory Retrieval

```bash
# Retrieve memories
curl -s "http://localhost:8765/api/v1/memories/?user_id=test" | jq '.items[] | {content: .content}'
```

### Verify Qdrant Storage

```bash
# Check collection has data
curl -s "http://localhost:6333/collections/openmemory" | jq '.result.points_count'
# Should show: 1 or more
```

## Performance Comparison

| Aspect | OpenAI | Ollama (Local) |
|--------|--------|----------------|
| **Speed** | ~1-2 seconds | ~4-5 seconds first, ~2-3 subsequent |
| **Cost** | $0.0001-0.0004 per memory | Free |
| **Privacy** | Data sent to OpenAI | Fully local |
| **Availability** | Requires internet | Works offline |
| **RAM Usage** | Minimal | ~4GB (mistral model) |

## Switching Back to OpenAI

If you want to switch back:

### 1. Stop API

```bash
docker-compose stop openmemory-mcp
```

### 2. Recreate Collections (1536 dimensions)

```bash
curl -X DELETE "http://localhost:6333/collections/openmemory"

curl -X PUT "http://localhost:6333/collections/openmemory" \
  -H "Content-Type: application/json" \
  -d '{"vectors": {"size": 1536, "distance": "Cosine"}}'
```

### 3. Start API

```bash
docker-compose start openmemory-mcp
sleep 10
```

### 4. Update Configuration

```bash
# Update LLM
curl -X PUT "http://localhost:8765/api/v1/config/mem0/llm" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "config": {
      "model": "gpt-4o-mini",
      "temperature": 0.1,
      "max_tokens": 2000,
      "api_key": "env:OPENAI_API_KEY"
    }
  }'

# Update Embedder
curl -X PUT "http://localhost:8765/api/v1/config/mem0/embedder" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "config": {
      "model": "text-embedding-3-small",
      "api_key": "env:OPENAI_API_KEY"
    }
  }'
```

## Troubleshooting

### Error: "Memory client is not available"

**Cause:** Configuration not initialized or Ollama unreachable

**Solution:**
```bash
# Check Ollama from inside container
docker exec openmemory-mcp curl http://host.docker.internal:11434/api/tags

# If fails, check Ollama on host
curl http://localhost:11434/api/tags

# Restart API
docker-compose restart openmemory-mcp
sleep 10
```

### Error: "Vector dimension error: expected 1536, got 768"

**Cause:** Forgot to recreate Qdrant collection with 768 dimensions

**Solution:** Go back to Step 3 and recreate collection

### Slow Memory Creation (10+ seconds)

**Cause:** Normal on first run (model loading)

**Check:**
```bash
# Monitor Ollama
ollama ps

# Check loaded models
curl http://localhost:11434/api/ps
```

### Models Not Found

```bash
# Verify models are pulled
ollama list

# Pull if missing
ollama pull mistral:7b-instruct-q4_K_M
ollama pull nomic-embed-text:latest
```

## Using Podman Instead of Docker

If using Podman, change `host.docker.internal` to `host.containers.internal` in all API calls:

```bash
curl -X PUT "http://localhost:8765/api/v1/config/mem0/llm" \
  -d '{
    "provider": "ollama",
    "config": {
      "ollama_base_url": "http://host.containers.internal:11434"
      ...
    }
  }'
```

## Environment Variables (Optional)

For easier switching, you can set environment variables:

```bash
# Create .env.ollama
cat > api/.env.ollama << 'EOF'
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=mistral:7b-instruct-q4_K_M
EMBEDDINGS_PROVIDER=ollama
EMBEDDINGS_MODEL=nomic-embed-text:latest
EMBEDDING_DIMS=768
EOF

# Use it
cp api/.env.ollama api/.env
docker-compose restart
```

## Summary

**Advantages of Ollama:**
- ✅ Free (no API costs)
- ✅ Private (all data stays local)
- ✅ Offline capable
- ✅ Good performance

**Trade-offs:**
- ⚠️ Slower than OpenAI (~2-4x)
- ⚠️ Requires ~4GB RAM for models
- ⚠️ Requires recreating vector collections (dimension change)

For most personal use cases, Ollama is an excellent choice!

