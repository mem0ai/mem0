#!/bin/sh
set -e

# Ensure the working directory is correct
cd /app

echo "Replacing runtime environment variables..."

# Replace placeholder strings with runtime environment values
# These placeholders are set at build time and replaced at container startup
PLACEHOLDER_USER_ID="__RUNTIME_USER_ID__"
PLACEHOLDER_API_URL="__RUNTIME_API_URL__"

# Get runtime values or use defaults
RUNTIME_USER_ID="${NEXT_PUBLIC_USER_ID:-user}"
RUNTIME_API_URL="${NEXT_PUBLIC_API_URL:-http://localhost:8765}"

echo "  User ID: ${RUNTIME_USER_ID}"
echo "  API URL: ${RUNTIME_API_URL}"

# Replace in all built JavaScript files
find .next/static -type f -name "*.js" -exec sed -i \
  -e "s|${PLACEHOLDER_USER_ID}|${RUNTIME_USER_ID}|g" \
  -e "s|${PLACEHOLDER_API_URL}|${RUNTIME_API_URL}|g" \
  {} \;

# Also replace in server-side chunks
find .next/server -type f -name "*.js" -exec sed -i \
  -e "s|${PLACEHOLDER_USER_ID}|${RUNTIME_USER_ID}|g" \
  -e "s|${PLACEHOLDER_API_URL}|${RUNTIME_API_URL}|g" \
  {} \;

echo "✓ Environment variables replaced successfully"

# Execute the container's main process (CMD in Dockerfile)
exec "$@"