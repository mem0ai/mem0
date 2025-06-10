#!/bin/bash
# Jean Memory API Start Script

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo -e "${BLUE}🚀 Starting Jean Memory API Server${NC}"
echo -e "${BLUE}=================================${NC}"

# Check if virtual environment exists
if [ ! -d "$SCRIPT_DIR/openmemory/venv" ]; then
    echo -e "${RED}❌ Virtual environment not found!${NC}"
    echo -e "${YELLOW}Run ./setup-local-complete.sh first${NC}"
    exit 1
fi

# Check if Docker containers are running
if ! docker ps | grep -q jeanmemory_postgres_service; then
    echo -e "${RED}❌ PostgreSQL container is not running!${NC}"
    echo -e "${YELLOW}Run: docker-compose up -d${NC}"
    exit 1
fi

if ! docker ps | grep -q jeanmemory_qdrant_service; then
    echo -e "${RED}❌ Qdrant container is not running!${NC}"
    echo -e "${YELLOW}Run: docker-compose up -d${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker containers are running${NC}"

# Kill any existing process on port 8765
if lsof -ti:8765 > /dev/null 2>&1; then
    echo -e "${YELLOW}Killing existing process on port 8765...${NC}"
    kill -9 $(lsof -ti:8765) 2>/dev/null || true
    sleep 2
fi

# Navigate to the API directory
cd "$SCRIPT_DIR/openmemory"

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source venv/bin/activate

# Ensure we're in the API directory
cd api

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ API .env file not found!${NC}"
    echo -e "${YELLOW}Run ./setup-local-complete.sh first${NC}"
    exit 1
fi

# Export environment variables
export $(grep -v '^#' .env | xargs)

# Verify critical environment variables
if [ -z "$DATABASE_URL" ]; then
    echo -e "${RED}❌ DATABASE_URL not set in .env${NC}"
    exit 1
fi

if [ -z "$QDRANT_HOST" ]; then
    echo -e "${RED}❌ QDRANT_HOST not set in .env${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Environment configured${NC}"

# Test database connection
echo -e "${YELLOW}Testing database connection...${NC}"
if PGPASSWORD=memory_password psql -h 127.0.0.1 -U jean_memory -d jean_memory_db -c "SELECT 1;" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Database connection successful${NC}"
else
    echo -e "${RED}❌ Cannot connect to database${NC}"
    exit 1
fi

# Test Qdrant connection
echo -e "${YELLOW}Testing Qdrant connection...${NC}"
if curl -s http://localhost:6333/collections > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Qdrant connection successful${NC}"
else
    echo -e "${RED}❌ Cannot connect to Qdrant${NC}"
    exit 1
fi

# Start the API server
echo -e "\n${GREEN}🚀 Starting API server on http://localhost:8765${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop${NC}\n"

# Run uvicorn with proper error handling
python -m uvicorn main:app --host 0.0.0.0 --port 8765 --reload
