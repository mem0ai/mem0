#!/bin/bash

# Script to restart the UI container with clean caches
# This helps when the UI container becomes slow or unresponsive

echo "Stopping UI container..."
docker-compose stop ui

echo "Removing UI container..."
docker-compose rm -f ui

echo "Pruning unused volumes..."
docker volume prune -f

echo "Rebuilding UI container..."
docker-compose build ui

echo "Starting UI container..."
docker-compose up -d ui

echo "UI container restarted successfully."
echo "Tailing logs (Ctrl+C to exit):"
docker logs -f jeanmemory_ui_service 