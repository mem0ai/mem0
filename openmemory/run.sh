#!/bin/bash

set -e

# Get environment variables from user input or fallback
OPENAI_API_KEY="${OPENAI_API_KEY:-}"
USER="${USER:-$(whoami)}"
NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL:-http://localhost:8765}" # You can also make this configurable

# Print values
echo "🔐 Using OPENAI_API_KEY: ${OPENAI_API_KEY:+[provided]}"
echo "👤 Using USER: $USER"
echo "🌐 Using NEXT_PUBLIC_API_URL: $NEXT_PUBLIC_API_URL"

# Warn if OPENAI_API_KEY is missing
if [ -z "$OPENAI_API_KEY" ]; then
  echo "❌ OPENAI_API_KEY is not set. Please run the script like this:"
  echo "   OPENAI_API_KEY=your-key bash run.sh"
  exit 1
fi

# Check if the container "mem0_store" already exists and remove it if necessary
if [ $(docker ps -aq -f name=mem0_store) ]; then
  echo "⚠️ Found existing container 'mem0_store'. Removing it..."
  docker rm -f mem0_store
fi

# Run Qdrant
echo "🚀 Starting Qdrant..."
docker run -d \
  --name mem0_store \
  -p 6333:6333 \
  -v mem0_storage:/mem0/storage \
  qdrant/qdrant

# Check if the container "mem0_api" already exists and remove it if necessary
if [ $(docker ps -aq -f name=mem0_api) ]; then
  echo "⚠️ Found existing container 'mem0_api'. Removing it..."
  docker rm -f mem0_api
fi

# Create a custom network for the containers (instead of using --link)
docker network create mem0_network || echo "Network 'mem0_network' already exists."

# Run API container
echo "🚀 Starting API..."
docker run -d \
  --name mem0_api \
  --network mem0_network \
  -e OPENAI_API_KEY="$OPENAI_API_KEY" \
  -e USER="$USER" \
  -e NEXT_PUBLIC_API_URL="$NEXT_PUBLIC_API_URL" \
  -p 8765:8765 \
  -v "$(pwd)":/usr/src/openmemory \
  mem0/openmemory-mcp \
  sh -c "uvicorn main:app --host 0.0.0.0 --port 8765 --reload --workers 4"

echo "✅ OpenMemory is running at http://localhost:8765"

# Check if the container "mem0_ui" already exists and remove it if necessary
if [ $(docker ps -aq -f name=mem0_ui) ]; then
  echo "⚠️ Found existing container 'mem0_ui'. Removing it..."
  docker rm -f mem0_ui
fi

# Start the frontend
echo "🚀 Starting frontend..."
docker run -d \
  --name mem0_ui \
  --network mem0_network \
  -e NEXT_PUBLIC_API_URL="$NEXT_PUBLIC_API_URL" \
  -e NEXT_PUBLIC_USER_ID="$USER" \
  -p 3000:3000 \
  -v "$(pwd)":/usr/src/openmemory \
  mem0/openmemory-ui \
  sh -c "npm run dev"

echo "✅ Frontend is running at http://localhost:3000"
