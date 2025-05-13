#!/bin/bash

set -e

# Get environment variables from user input or fallback
OPENAI_API_KEY="${OPENAI_API_KEY:-}"
USER="${USER:-$(whoami)}"

# Print values
echo "🔐 Using OPENAI_API_KEY: ${OPENAI_API_KEY:+[provided]}"
echo "👤 Using USER: $USER"

# Warn if OPENAI_API_KEY is missing
if [ -z "$OPENAI_API_KEY" ]; then
  echo "❌ OPENAI_API_KEY is not set. Please run the script like this:"
  echo "   OPENAI_API_KEY=your-key bash run.sh"
  exit 1
fi

# Run Qdrant
echo "🚀 Starting Qdrant..."
docker run -d \
  --name mem0_store \
  -p 6333:6333 \
  -v mem0_storage:/mem0/storage \
  qdrant/qdrant

# Build API container
echo "🔧 Building API container..."
docker build -t mem0/openmemory-mcp .

# Run API container
echo "🚀 Starting API..."
docker run -d \
  --name mem0_api \
  -e OPENAI_API_KEY="$OPENAI_API_KEY" \
  -e USER="$USER" \
  --link mem0_store \
  -p 8765:8765 \
  -v "$(pwd)":/usr/src/openmemory \
  mem0/openmemory-mcp \
  sh -c "uvicorn main:app --host 0.0.0.0 --port 8765 --reload --workers 4"

echo "✅ OpenMemory is running at http://localhost:8765"
