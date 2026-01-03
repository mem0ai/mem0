#!/bin/bash

STACK_NAME="OpenMemory"
COMPOSE_FILE="docker-compose.yml"

echo "Starting or Updating the $STACK_NAME stack..."
echo "-------------------------------------"

# 1. Pull latest base images (Qdrant, Postgres)
echo "1. Pulling latest base images..."
docker compose -f $COMPOSE_FILE pull

# 2. Build custom images if needed (skip cache for fresh config)
echo "2. Building custom images (LM Studio + your user_id)..."
docker compose -f $COMPOSE_FILE build --no-cache

# 3. Start the stack
echo "3. Starting the stack..."
docker compose -f $COMPOSE_FILE up -d

if [ $? -ne 0 ]; then
    echo "Error: Failed to start. Check logs: docker compose -f $COMPOSE_FILE logs -f"
    exit 1
fi

# 4. Cleanup old images
echo "4. Removing old/unused images..."
docker image prune -f

# 5. Status
echo "5. Stack status:"
docker compose -f $COMPOSE_FILE ps

echo "-------------------------------------"
echo "OpenMemory is running!"
echo "API: http://localhost:10003/docs"
echo "UI: http://localhost:10004"
echo ""
echo "Load your models in LM Studio, then test adding a memory in the UI."