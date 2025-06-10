#!/bin/bash

# Script to restart the local UI development process
# Use this when you need to restart the UI without restarting the backend

# Colors for better readability
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}i${NC} Finding and stopping any running UI processes..."

# Find and kill any running Next.js dev processes
UI_PID=$(ps aux | grep "npm run dev" | grep -v grep | awk '{print $2}')
if [ -n "$UI_PID" ]; then
    echo -e "${YELLOW}⚠${NC} Stopping existing Next.js process (PID: $UI_PID)..."
    kill -9 $UI_PID
    sleep 2
    echo -e "${GREEN}✓${NC} Previous UI process stopped"
else
    echo -e "${BLUE}i${NC} No running UI process found"
fi

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Clear Next.js cache
echo -e "${BLUE}i${NC} Clearing Next.js cache..."
if [ -d "$PROJECT_ROOT/openmemory/ui/.next" ]; then
    rm -rf "$PROJECT_ROOT/openmemory/ui/.next/cache"
    echo -e "${GREEN}✓${NC} Next.js cache cleared"
fi

# Start the UI in the background
echo -e "${BLUE}i${NC} Starting local UI development server..."
"$SCRIPT_DIR/local-dev-ui.sh" &

echo -e "${GREEN}✓${NC} UI restart process completed!"
echo -e "${BLUE}i${NC} The UI will be available at ${GREEN}http://localhost:3000${NC} in a few moments" 